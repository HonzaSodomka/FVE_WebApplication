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