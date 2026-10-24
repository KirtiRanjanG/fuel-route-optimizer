import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from fuel.models import FuelStation

class Command(BaseCommand):
    help = "Import the assessment fuel-price CSV."
    def add_arguments(self, parser):
        parser.add_argument("--file", default="fuel-prices-for-be-assessment.csv")
    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"CSV not found: {path.resolve()}")
        required = {"OPIS Truckstop ID","Truckstop Name","Address","City","State","Rack ID","Retail Price"}
        created = updated = skipped = 0
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise CommandError("CSV columns do not match the assessment dataset.")
            for row in reader:
                try:
                    station_id = int(row["OPIS Truckstop ID"])
                    price = float(Decimal(row["Retail Price"]))
                    rack = int(row["Rack ID"]) if row.get("Rack ID") else None
                    if price <= 0: raise ValueError()
                except (ValueError, TypeError, InvalidOperation):
                    skipped += 1
                    continue
                _, was_created = FuelStation.objects.update_or_create(opis_id=station_id, defaults={
                    "name": (row.get("Truckstop Name") or "").strip(),
                    "address": (row.get("Address") or "").strip(),
                    "city": (row.get("City") or "").strip(),
                    "state": (row.get("State") or "").strip(),
                    "rack_id": rack, "retail_price": price,
                })
                created += int(was_created)
                updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(
            f"Import complete. Created={created}, updated={updated}, skipped={skipped}, total={FuelStation.objects.count()}"
        ))
