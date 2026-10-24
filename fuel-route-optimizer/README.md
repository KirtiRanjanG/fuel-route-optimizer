# Fuel Route Optimizer API

## Setup (Windows PowerShell)
Place `fuel-prices-for-be-assessment.csv` next to `manage.py`.

```powershell
py -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py makemigrations fuel
python manage.py migrate
python manage.py import_fuel_prices --file fuel-prices-for-be-assessment.csv
python manage.py runserver
```

If `py` is unavailable, use `python`.

## Postman tests
Health check:
- GET `http://127.0.0.1:8000/api/health/`

Route:
- POST `http://127.0.0.1:8000/api/route-optimizer/`
- Header `Content-Type: application/json`
- Body > raw > JSON:
```json
{
  "start": "Chicago, Illinois, USA",
  "finish": "Indianapolis, Indiana, USA",
  "mpg": 10,
  "max_range_miles": 500
}
```

## Important limitations
The assessment CSV has 8,151 fuel stations and prices but no coordinates. This prototype gets mapped station candidates from OpenStreetMap Overpass, then matches station names to CSV names. This matching can be imperfect. Short routes return route geometry and a cost estimate; long routes require price-matched mapped stations and may return a documented 502 error if none can be matched. Prices are not live. Cost is an estimate because the assessment does not specify tank capacity or starting fuel quantity.

External services used:
- Nominatim for geocoding (cached 24 hours)
- OSRM public demo for driving routes (cached 12 hours)
- Overpass API for mapped fuel stations (one batched request per uncached route, cached 6 hours)

Public demo services have fair-use limits and no uptime guarantee. Do not load-test them. A production implementation should geocode the CSV in a controlled offline process and use PostGIS for spatial matching.
