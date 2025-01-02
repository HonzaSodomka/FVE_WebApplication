from django.db import models

class PriceData(models.Model):
    date = models.DateField()
    hour = models.IntegerField()
    price_czk = models.IntegerField()
    level = models.CharField(max_length=10)  # 'low', 'medium', 'high'
    level_num = models.IntegerField()

    class Meta:
        # Zajistíme, že kombinace data a hodiny bude unikátní
        unique_together = ['date', 'hour']
        # Seřadíme podle data a hodiny
        ordering = ['date', 'hour']

    def __str__(self):
        return f"{self.date} {self.hour}:00 - {self.price_czk} CZK ({self.level})"

class SolarData(models.Model):
    timestamp = models.DateTimeField(unique=True)
    watts = models.FloatField(null=True)  # Okamžitý výkon
    watt_hours_period = models.FloatField()  # Výroba za danou periodu
    watt_hours_cumulative = models.FloatField()  # Kumulativní výroba za den
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
        ]
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.timestamp}: {self.watt_hours_period} Wh"