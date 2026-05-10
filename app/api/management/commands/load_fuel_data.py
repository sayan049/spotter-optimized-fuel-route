import csv
import time
import requests
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from api.models import TruckStop

class Command(BaseCommand):
    help = 'Load fuel stations from CSV and geocode them, keeping cheapest price per OPIS ID'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str)

    def handle(self, *args, **options):
        path = options['csv_path']
        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                opis = int(row['OPIS Truckstop ID'])
                state = row['State'].strip().upper()
                # Skip non‑US entries (Canadian provinces)
                if state in ('AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT'):
                    continue

                price = float(row['Retail Price'])

                existing = TruckStop.objects.filter(opis_id=opis).first()
                if existing and existing.price <= price:
                    # Already have a cheaper or equal price – skip this row
                    count += 1
                    continue

                point = existing.location if existing else None
                if point is None:
                    # Geocode only if we don't have coordinates yet
                    address = f"{row['Address']}, {row['City']}, {state}, USA"
                    try:
                        resp = requests.get(
                            'https://nominatim.openstreetmap.org/search',
                            params={'q': address, 'format': 'json', 'limit': 1},
                            headers={'User-Agent': 'SpotterAPI/1.0'},
                            timeout=10
                        )
                        data = resp.json()
                        if data:
                            point = Point(float(data[0]['lon']), float(data[0]['lat']), srid=4326)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Geocode failed: {address}, {e}"))
                    time.sleep(2)   # respect Nominatim's rate limit

                if existing:
                    existing.price = price
                    if point:
                        existing.location = point
                    existing.save()
                else:
                    TruckStop.objects.create(
                        opis_id=opis,
                        name=row['Truckstop Name'],
                        address=row['Address'],
                        city=row['City'],
                        state=state,
                        price=price,
                        location=point
                    )
                count += 1
                self.stdout.write(f"Processed row {count}: {row['Truckstop Name']}")

        self.stdout.write(self.style.SUCCESS(f"Finished processing {count} rows"))