from django.db import models

#FVE.Bakalarka.2025
class DashboardPassword(models.Model):
    password_hash = models.CharField(max_length=128)
    
    def __str__(self):
        return "Dashboard heslo"
    
    class Meta:
        verbose_name = "Dashboard heslo"
        verbose_name_plural = "Dashboard hesla"


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

    # Pro CYCLIC typ
    run_duration_min = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Minimální doba běhu cyklu (minuty)",
        help_text="Minimální doba, po kterou spotřebič běží v jednom cyklu"
    )
    run_duration_max = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Maximální doba běhu cyklu (minuty)",
        help_text="Maximální doba, po kterou spotřebič běží v jednom cyklu"
    )
    pause_duration_min = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Minimální doba pauzy mezi cykly (minuty)",
        help_text="Minimální doba mezi cykly běhu"
    )
    pause_duration_max = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Maximální doba pauzy mezi cykly (minuty)",
        help_text="Maximální doba mezi cykly běhu"
    )

    # Pro SCHEDULED a ON_DEMAND typy
    usage_duration = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Délka použití (minuty)",
        help_text="Jak dlouho spotřebič běží při jednom použití"
    )

    # Pro ON_DEMAND typ
    uses_per_window = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Počet použití v časovém okně",
        help_text="Kolikrát se spotřebič typicky použije v jednom časovém okně"
    )

    # Pro SCHEDULED a ON_DEMAND typy
    weekday_probability = models.FloatField(
        default=1.0,
        verbose_name="Pravděpodobnost použití (pracovní den)",
        help_text="Pravděpodobnost spuštění v časovém okně (pro plánované spotřebiče)"
    )
    weekend_probability = models.FloatField(
        default=1.0,
        verbose_name="Pravděpodobnost použití (víkend)",
        help_text="Pravděpodobnost spuštění v časovém okně (pro plánované spotřebiče)"
    )
    
    # Pro SCHEDULED a ON_DEMAND typy - časová okna kdy může běžet
    weekday_hours = models.JSONField(
        default=list,
        verbose_name="Časová okna (pracovní den)",
        help_text="Seznam časových oken ve formátu [[od1, do1], [od2, do2], ...], kde časy jsou v hodinách (0-24)"
    )
    weekend_hours = models.JSONField(
        default=list,
        verbose_name="Časová okna (víkend)",
        help_text="Seznam časových oken ve formátu [[od1, do1], [od2, do2], ...], kde časy jsou v hodinách (0-24)"
    )

    def save(self, *args, **kwargs):
        # Nastavení defaultních hodnot podle typu spotřebiče
        if self.appliance_type == 'CONSTANT':
            # Konstantní spotřebiče běží pořád stejně
            self.run_duration_min = None
            self.run_duration_max = None
            self.pause_duration_min = None
            self.pause_duration_max = None
            self.usage_duration = None
            self.uses_per_window = None
            self.weekday_probability = 1.0
            self.weekend_probability = 1.0
            self.weekday_hours = [[0, 24]]
            self.weekend_hours = [[0, 24]]
            
        elif self.appliance_type == 'CYCLIC':
            # Cyklické spotřebiče mají definované cykly, ale běží pořád
            self.usage_duration = None
            self.uses_per_window = None
            self.weekday_probability = 1.0
            self.weekend_probability = 1.0
            self.weekday_hours = [[0, 24]]
            self.weekend_hours = [[0, 24]]
            
        elif self.appliance_type == 'SCHEDULED':
            # Plánované spotřebiče mají definovanou délku běhu a časová okna
            self.run_duration_min = None
            self.run_duration_max = None
            self.pause_duration_min = None
            self.pause_duration_max = None
            self.uses_per_window = None
            
        elif self.appliance_type == 'ON_DEMAND':
            # Spotřebiče na vyžádání mají definovanou délku použití, 
            # počet použití v okně a časová okna
            self.run_duration_min = None
            self.run_duration_max = None
            self.pause_duration_min = None
            self.pause_duration_max = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_appliance_type_display()}) - {self.house.name}"

    class Meta:
        verbose_name = "Spotřebič"
        verbose_name_plural = "Spotřebiče"