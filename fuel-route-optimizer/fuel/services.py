import math, re, hashlib
from difflib import SequenceMatcher
import requests
from django.core.cache import cache
from .models import FuelStation

HEADERS = {"User-Agent": "FuelRouteOptimizerAssessment/1.0"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OSRM = "https://router.project-osrm.org/route/v1/driving"
OVERPASS = "https://overpass-api.de/api/interpreter"

class ExternalServiceError(Exception): pass

def get_json(url, params=None, data=None, timeout=25):
    try:
        if data is None:
            r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        else:
            r = requests.post(url, data=data, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as exc:
        raise ExternalServiceError("A free map service did not respond. Retry later; public services have fair-use limits.") from exc

def geocode(place):
    key = "geocode:" + place.casefold()
    cached = cache.get(key)
    if cached: return cached
    data = get_json(NOMINATIM, params={"q": place, "format": "jsonv2", "limit": 1, "countrycodes": "us"})
    if not data: raise ExternalServiceError(f"Could not find a US location for: {place}")
    result = {"lat":float(data[0]["lat"]), "lon":float(data[0]["lon"]), "display_name":data[0].get("display_name", place)}
    cache.set(key, result, 86400)
    return result

def miles_between(a, b):
    lat1, lon1 = a; lat2, lon2 = b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 3958.7613 * 2 * math.asin(math.sqrt(min(1, h)))

def get_route(start, finish):
    a, b = geocode(start), geocode(finish)
    key = f"route:{a['lat']:.4f},{a['lon']:.4f}:{b['lat']:.4f},{b['lon']:.4f}"
    route = cache.get(key)
    if not route:
        data = get_json(f"{OSRM}/{a['lon']},{a['lat']};{b['lon']},{b['lat']}",
                        params={"overview":"full","geometries":"geojson","steps":"false"})
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ExternalServiceError("Routing service could not calculate this route.")
        r = data["routes"][0]
        route = {"distance_miles":r["distance"]/1609.344,"duration_seconds":r["duration"],"geometry":r["geometry"]}
        cache.set(key, route, 43200)
    return a, b, route

def sample_points(coords, limit=16):
    if len(coords) <= limit: return coords
    return [coords[round(i*(len(coords)-1)/(limit-1))] for i in range(limit)]

def osm_fuel_stations(geometry):
    coords = geometry.get("coordinates", [])
    samples = sample_points(coords)
    if not samples: return []
    cache_key = "overpass:" + hashlib.md5(repr([(round(x,3),round(y,3)) for x,y in samples]).encode()).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None: return cached
    clauses = []
    for lon, lat in samples:
        clauses += [f'node(around:10000,{lat},{lon})[amenity=fuel];',
                    f'way(around:10000,{lat},{lon})[amenity=fuel];']
    query = "[out:json][timeout:20];(" + "".join(clauses) + ");out center tags;"
    data = get_json(OVERPASS, data={"data":query}, timeout=30)
    seen, result = set(), []
    for item in data.get("elements", []):
        tags = item.get("tags", {})
        name = tags.get("name") or tags.get("brand") or tags.get("operator")
        lat = item.get("lat", item.get("center",{}).get("lat"))
        lon = item.get("lon", item.get("center",{}).get("lon"))
        if not name or lat is None or lon is None: continue
        key = (name.casefold(), round(float(lat),4), round(float(lon),4))
        if key in seen: continue
        seen.add(key)
        result.append({"name":name,"latitude":float(lat),"longitude":float(lon)})
    cache.set(cache_key, result, 21600)
    return result

def normalize(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())

def match_price(osm_name, rows):
    target = normalize(osm_name)
    best, best_score = None, 0
    for row in rows:
        name = normalize(row.name)
        if not name: continue
        score = SequenceMatcher(None, target, name).ratio()
        if target == name: score = 1
        if score > best_score: best, best_score = row, score
    if best is not None and best_score >= 0.80:
        return best, round(best_score, 2)
    return None, None

def build_route_result(start, finish, mpg=10, max_range_miles=500):
    a, b, route = get_route(start, finish)
    distance = route["distance_miles"]
    coords = route["geometry"].get("coordinates", [])
    if distance <= 0 or not coords: raise ExternalServiceError("Route returned no usable geometry.")
    # A single batched Overpass query gets mapped stations near sampled route points.
    osm = osm_fuel_stations(route["geometry"]) if distance > max_range_miles else []
    rows = list(FuelStation.objects.only("name","retail_price","city","state"))
    cumulative = [0.0]
    for i in range(1, len(coords)):
        cumulative.append(cumulative[-1] + miles_between((coords[i-1][1],coords[i-1][0]),(coords[i][1],coords[i][0])))
    geo_total = cumulative[-1] or 1
    candidates = []
    for station in osm:
        nearest_i, nearest_coord = min(enumerate(coords), key=lambda pair: miles_between(
            (station["latitude"], station["longitude"]), (pair[1][1], pair[1][0])))
        offroute = miles_between(
            (station["latitude"], station["longitude"]),
            (nearest_coord[1], nearest_coord[0])
        )
        if offroute > 6: continue
        row, confidence = match_price(station["name"], rows)
        if not row: continue
        progress = min(distance, cumulative[nearest_i]/geo_total*distance)
        candidates.append({
            "station_name":station["name"],"latitude":station["latitude"],"longitude":station["longitude"],
            "price_per_gallon_usd":round(float(row.retail_price),3),
            "matched_csv_station":row.name,"matched_csv_city":row.city,"matched_csv_state":row.state,
            "match_confidence":confidence,"distance_from_route_miles":round(offroute,2),
            "route_progress_miles":round(progress,1)
        })
    candidates.sort(key=lambda s:s["route_progress_miles"])
    stops, current = [], 0.0
    while distance-current > max_range_miles:
        reachable = [s for s in candidates if current < s["route_progress_miles"] <= current+max_range_miles]
        if not reachable:
            raise ExternalServiceError("Route found, but no price-matched mapped station was found within range. The CSV has no coordinates, so station matching needs data enrichment.")
        chosen = min(reachable, key=lambda s:(s["price_per_gallon_usd"],-s["route_progress_miles"]))
        stops.append(chosen)
        current = chosen["route_progress_miles"]
        candidates = [s for s in candidates if s["route_progress_miles"] > current]
    gallons = distance / mpg
    if stops:
        assumed_price = sum(s["price_per_gallon_usd"] for s in stops)/len(stops)
        method = "estimated route gallons multiplied by average selected-stop price; exact purchase quantities are not specified"
    else:
        cheapest = FuelStation.objects.order_by("retail_price").first()
        assumed_price = float(cheapest.retail_price) if cheapest else None
        method = "estimated route gallons multiplied by the lowest price in the supplied CSV; no en-route stop required"
    cost = gallons*assumed_price if assumed_price is not None else None
    return {
        "start":{"input":start,"resolved":a["display_name"],"latitude":a["lat"],"longitude":a["lon"]},
        "finish":{"input":finish,"resolved":b["display_name"],"latitude":b["lat"],"longitude":b["lon"]},
        "route":{"distance_miles":round(distance,2),"duration_minutes":round(route["duration_seconds"]/60,1),
                 "geometry":route["geometry"],"geometry_format":"GeoJSON LineString; coordinates are [longitude, latitude]"},
        "vehicle":{"mpg":mpg,"maximum_range_miles":max_range_miles,"assumption":"vehicle starts with a full tank"},
        "fuel":{"gallons_consumed_estimate":round(gallons,2),"estimated_total_cost_usd":round(cost,2) if cost is not None else None,
                "cost_method":method,"price_source":"uploaded CSV; prices are not live"},
        "fuel_stops":stops,
        "matching":{"mapped_stations_found":len(osm),"price_matched_stations_near_route":len(candidates),
                    "warning":"Name-based matching is approximate. Verify station/price matches; CSV has no coordinates."}
    }
