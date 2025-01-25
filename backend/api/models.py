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
    
class House(models.Model):
    name = models.CharField(max_length=100, verbose_name="Název domu")
    solar_power = models.FloatField(verbose_name="Výkon solárních panelů (kWp)")
    battery_capacity = models.FloatField(verbose_name="Kapacita baterie (kWh)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.solar_power} kWp, {self.battery_capacity} kWh)"
        
    class Meta:
        verbose_name = "Dům"
        verbose_name_plural = "Domy"

class Appliance(models.Model):
   # Základní pole
   house = models.ForeignKey(
       House,
       on_delete=models.CASCADE,
       related_name='appliances',
       verbose_name="Dům"
   )
   name = models.CharField(max_length=100, verbose_name="Název spotřebiče")
   power_consumption = models.IntegerField(verbose_name="Spotřeba (W)")
   
   APPLIANCE_TYPES = [
       ('CONSTANT', 'Konstantní spotřeba'),      # např. router
       ('CYCLIC', 'Cyklická spotřeba'),         # např. lednice
       ('SCHEDULED', 'Plánovaná spotřeba'),      # např. pračka
       ('ON_DEMAND', 'Spotřeba na vyžádání'),    # např. konvice
   ]
   appliance_type = models.CharField(
       max_length=20,
       choices=APPLIANCE_TYPES,
       verbose_name="Typ spotřebiče"
   )

   # Stavové proměnné pro CYCLIC
   in_standby = models.BooleanField(default=True, null=True)
   remaining_minutes = models.IntegerField(default=0, null=True)

   # Konfigurační pole pro CYCLIC
   run_duration_min = models.IntegerField(
       null=True, 
       blank=True,
       verbose_name="Minimální doba běhu cyklu (minuty)",
   )
   run_duration_max = models.IntegerField(
       null=True, 
       blank=True,
       verbose_name="Maximální doba běhu cyklu (minuty)",
   )
   pause_duration_min = models.IntegerField(
       null=True, 
       blank=True,
       verbose_name="Minimální doba pauzy mezi cykly (minuty)",
   )
   pause_duration_max = models.IntegerField(
       null=True, 
       blank=True,
       verbose_name="Maximální doba pauzy mezi cykly (minuty)",
   )

   # Stavové proměnné pro SCHEDULED/ON_DEMAND
   is_active = models.BooleanField(default=False, null=True)
   next_start_time = models.DateTimeField(null=True, blank=True)  # pro SCHEDULED
   planned_starts = models.JSONField(default=list, null=True)     # pro ON_DEMAND
   
   # Konfigurační pole pro SCHEDULED/ON_DEMAND
   usage_duration_min = models.IntegerField(
       null=True, 
       blank=True,
       verbose_name="Minimální doba běhu (minuty)",
   )
   usage_duration_max = models.IntegerField(
       null=True, 
       blank=True,
       verbose_name="Maximální doba běhu (minuty)",
   )
   weekday_hours = models.JSONField(
       default=list,
       verbose_name="Časová okna (pracovní den)",
       help_text="Seznam časových oken ve formátu [{start: int, end: int, probability: float, uses: int}]"
   )
   weekend_hours = models.JSONField(
       default=list,
       verbose_name="Časová okna (víkend)",
       help_text="Seznam časových oken ve formátu [{start: int, end: int, probability: float, uses: int}]"
   )

   def save(self, *args, **kwargs):
       # Nastavení defaultních hodnot podle typu spotřebiče
       if self.appliance_type == 'CONSTANT':
           self.in_standby = None
           self.remaining_minutes = None
           self.is_active = None
           self.next_start_time = None
           self.planned_starts = None
           self.run_duration_min = None
           self.run_duration_max = None
           self.pause_duration_min = None
           self.pause_duration_max = None
           self.usage_duration_min = None
           self.usage_duration_max = None
           self.weekday_hours = []
           self.weekend_hours = []
           
       elif self.appliance_type == 'CYCLIC':
           self.is_active = None
           self.next_start_time = None
           self.planned_starts = None
           self.usage_duration_min = None
           self.usage_duration_max = None
           self.weekday_hours = []
           self.weekend_hours = []
           
       elif self.appliance_type == 'SCHEDULED':
           self.in_standby = None
           self.run_duration_min = None
           self.run_duration_max = None
           self.pause_duration_min = None
           self.pause_duration_max = None
           self.planned_starts = None
           
       elif self.appliance_type == 'ON_DEMAND':
           self.in_standby = None
           self.run_duration_min = None
           self.run_duration_max = None
           self.pause_duration_min = None
           self.pause_duration_max = None
           self.next_start_time = None

       super().save(*args, **kwargs)

   def __str__(self):
       return f"{self.name} ({self.get_appliance_type_display()}) - {self.house.name}"

   class Meta:
       verbose_name = "Spotřebič"
       verbose_name_plural = "Spotřebiče"