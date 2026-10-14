from django.db import models


class Station(models.Model):
    """One fuel station (deduplicated by OPIS id) with city-level coordinates."""

    opis_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    price = models.FloatField(help_text="Retail price, USD per gallon")
    latitude = models.FloatField()
    longitude = models.FloatField()
    # True when the coordinates are the city centre, not the exact pump location.
    is_approximate = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) ${self.price:.3f}"
