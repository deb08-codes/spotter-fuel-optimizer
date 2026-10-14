import time

from django.core.management.base import BaseCommand

from routing.models import Station
from routing.services.city_lookup import city_key, load_city_index
from routing.services.fuel_data_service import load_fuel_data
from routing.services.station_matcher import reset_station_index


class Command(BaseCommand):
    help = (
        "One-time import: clean + dedupe the fuel CSV, attach city-level "
        "coordinates and store everything in the Station table."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--nominatim",
            action="store_true",
            help="Geocode cities missing from the offline list via Nominatim (1 req/sec).",
        )

    def handle(self, *args, **options):
        df = load_fuel_data()
        index = load_city_index()
        self.stdout.write(f"{len(df)} unique US stations after cleaning")

        keys = [city_key(c, s) for c, s in zip(df["City"], df["State"])]
        missing = sorted({(c, s) for c, s, k in zip(df["City"], df["State"], keys) if k not in index})

        if missing and options["nominatim"]:
            self._geocode_missing(missing, index)

        rows, skipped = [], 0
        for record, key in zip(df.to_dict("records"), keys):
            coords = index.get(key)
            if coords is None:
                skipped += 1
                continue
            rows.append(
                Station(
                    opis_id=record["OPIS Truckstop ID"],
                    name=record["Truckstop Name"],
                    address=record["Address"],
                    city=record["City"],
                    state=record["State"],
                    price=float(record["Retail Price"]),
                    latitude=coords[0],
                    longitude=coords[1],
                    is_approximate=True,
                )
            )

        Station.objects.bulk_create(
            rows,
            batch_size=500,
            update_conflicts=True,
            unique_fields=["opis_id"],
            update_fields=["name", "address", "city", "state", "price", "latitude", "longitude", "is_approximate"],
        )
        reset_station_index()
        self.stdout.write(self.style.SUCCESS(f"Imported {len(rows)} stations; {skipped} skipped (no coordinates)"))
        if skipped and not options["nominatim"]:
            self.stdout.write("Re-run with --nominatim to geocode the skipped cities.")

    def _geocode_missing(self, missing, index):
        from geopy.geocoders import Nominatim

        geolocator = Nominatim(user_agent="spotter_fuel_optimizer_assessment", timeout=10)
        for city, state in missing:
            try:
                loc = geolocator.geocode(f"{city}, {state}, USA", country_codes="us")
            except Exception:
                loc = None
            if loc:
                index[city_key(city, state)] = (loc.latitude, loc.longitude)
            time.sleep(1.1)
