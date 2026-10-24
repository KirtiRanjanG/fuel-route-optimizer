from django.db import models
class FuelStation(models.Model):
    opis_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=10)
    rack_id = models.IntegerField(null=True, blank=True)
    retail_price = models.FloatField()
    class Meta:
        indexes = [models.Index(fields=["state", "city"]), models.Index(fields=["retail_price"])]
    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"
