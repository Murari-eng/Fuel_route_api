from django.db import models


class FuelStation(models.Model):
    station_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    price_per_gallon = models.DecimalField(
        max_digits=8,
        decimal_places=3,
    )
    address = models.CharField(max_length=500, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return f"{self.name} - ${self.price_per_gallon}/gallon"

    class Meta:
        ordering = ["price_per_gallon", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=['station_id'],
                name='unique_station_id'
            )
        ]