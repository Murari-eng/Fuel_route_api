# routing/management/commands/load_fuel.py
import csv
from django.core.management.base import BaseCommand
from django.conf import settings
from fuel_route_optimizer.models import FuelStation


class Command(BaseCommand):
    help = "Load fuel stations from fuel_prices.csv (OPIS format with lat/lon)."

    def handle(self, *args, **kwargs):
        path = settings.BASE_DIR / "data" / "fuel_prices_enriched.csv"

        if not path.exists():
            self.stderr.write(self.style.ERROR(f"❌ File not found: {path}"))
            return

        self.stdout.write(f"📖 Reading {path}")
        FuelStation.objects.all().delete()

        batch = []
        skipped = 0
        seen = set()

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # --- Map CSV columns to model fields ---
                station_id = (row.get("OPIS Truckstop ID") or "").strip()
                name       = (row.get("Truckstop Name") or "").strip()
                address    = (row.get("Address") or "").strip()
                state      = (row.get("State") or "").strip().upper()
                price_raw  = (row.get("Retail Price") or "").strip()
                lat_raw    = (row.get("latitude") or "").strip()
                lon_raw    = (row.get("longitude") or "").strip()

                # Skip rows missing essentials
                if not (station_id and name and price_raw and lat_raw and lon_raw):
                    skipped += 1
                    continue

                # Dedupe (OPIS has duplicate rows like two PILOT #1243)
                key = (station_id, name)
                if key in seen:
                    continue
                seen.add(key)

                try:
                    lat = float(lat_raw)
                    lon = float(lon_raw)
                    price = float(price_raw)
                except ValueError:
                    skipped += 1
                    continue

                batch.append(FuelStation(
                    station_id=station_id,
                    name=name,
                    latitude=lat,
                    longitude=lon,
                    price_per_gallon=price,
                    address=address,
                    state=state,
                ))

        FuelStation.objects.bulk_create(batch, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(
            f"✅ Loaded {len(batch)} stations (skipped {skipped})"
        ))