from django.contrib.gis.db import models

class TruckStop(models.Model):
    opis_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=5)
    price = models.FloatField()
    location = models.PointField(geography=True, spatial_index=True, null=True, blank=True)

    def __str__(self):
        return f"{self.name} (${self.price:.2f})"