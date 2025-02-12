from django.db import models
from datetime import date

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
    # Risk level pro nabíjení
    RISK_LEVELS = [
        ('LOW', 'Nízké riziko'),      # Jistota energie za cenu vyšších nákladů
        ('MEDIUM', 'Střední riziko'),  # Vyvážený přístup
        ('HIGH', 'Vysoké riziko'),     # Agresivní optimalizace ceny s rizikem drahého dobíjení
    ]

    # Základní informace
    name = models.CharField(max_length=100, verbose_name="Název domu")
    solar_power = models.FloatField(verbose_name="Výkon solárních panelů (kWp)")
    battery_capacity = models.FloatField(verbose_name="Kapacita baterie (kWh)")
    is_active = models.BooleanField(default=False, verbose_name="Aktivní simulace")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Parametry baterie
    current_battery_level = models.FloatField(
        default=0,
        verbose_name="Aktuální stav baterie (kWh)"
    )
    min_battery_level = models.FloatField(
        default=10,
        verbose_name="Minimální povolená úroveň baterie (%)"
    )
    max_charging_power = models.FloatField(
        default=0,  # Přidáno default=0
        verbose_name="Maximální nabíjecí výkon (kW)",
        help_text="Jak rychle lze baterii nabíjet"
    )
    max_discharging_power = models.FloatField(
        default=0,  # Přidáno default=0
        verbose_name="Maximální vybíjecí výkon (kW)",
        help_text="Jak rychle lze baterii vybíjet"
    )
    charging_efficiency = models.FloatField(
        default=90,
        verbose_name="Účinnost nabíjení (%)"
    )
    discharging_efficiency = models.FloatField(
        default=90,
        verbose_name="Účinnost vybíjení (%)"
    )
    
    # Risk level
    risk_level = models.CharField(
        max_length=6,
        choices=RISK_LEVELS,
        default='MEDIUM',
        verbose_name="Úroveň rizika",
        help_text="""
            NÍZKÉ: Nabíjí i za vyšší ceny pro zajištění dostatku energie
            STŘEDNÍ: Vyvážený přístup mezi cenou a jistotou energie
            VYSOKÉ: Riskantní optimalizace ceny, možnost nutnosti drahého dobíjení
        """
    )
    
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
    standby_power = models.IntegerField(
        null=True, 
        blank=True,
        verbose_name="Spotřeba v pohotovostním režimu (W)",
        help_text="Povinné pro cyklické spotřebiče, volitelné pro plánované a na vyžádání"
    )
    
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
    remaining_minutes_list = models.JSONField(                     # pro ON_DEMAND - seznam běžících časů
        default=list,
        null=True,
        blank=True,
        verbose_name="Seznam zbývajících minut pro paralelní běhy"
    )
    
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
        null=True,
        blank=True,
        verbose_name="Časová okna (pracovní den)",
        help_text="Seznam časových oken ve formátu [{start: int, end: int, probability: float, uses: int}]"
    )
    weekend_hours = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Časová okna (víkend)",
        help_text="Seznam časových oken ve formátu [{start: int, end: int, probability: float, uses: int}]"
    )

    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        
        # Validace standby_power podle typu spotřebiče
        if self.appliance_type == 'CYCLIC' and not self.standby_power:
            raise ValidationError('Pro cyklické spotřebiče je povinné vyplnit spotřebu v pohotovostním režimu')
        
        # Nastavení defaultních hodnot podle typu spotřebiče
        if self.appliance_type == 'CONSTANT':
            self.standby_power = None
            self.in_standby = None
            self.remaining_minutes = None
            self.is_active = None
            self.next_start_time = None
            self.planned_starts = None
            self.remaining_minutes_list = None
            self.run_duration_min = None
            self.run_duration_max = None
            self.pause_duration_min = None
            self.pause_duration_max = None
            self.usage_duration_min = None
            self.usage_duration_max = None
            self.weekday_hours = None
            self.weekend_hours = None
            
        elif self.appliance_type == 'CYCLIC':
            self.is_active = None
            self.next_start_time = None
            self.planned_starts = None
            self.remaining_minutes_list = None
            self.usage_duration_min = None
            self.usage_duration_max = None
            self.weekday_hours = None
            self.weekend_hours = None
            
        elif self.appliance_type == 'SCHEDULED':
            self.in_standby = None
            self.remaining_minutes_list = None
            self.run_duration_min = None
            self.run_duration_max = None
            self.pause_duration_min = None
            self.pause_duration_max = None
            self.planned_starts = None
            
        elif self.appliance_type == 'ON_DEMAND':
            self.in_standby = None
            self.remaining_minutes = None
            self.run_duration_min = None
            self.run_duration_max = None
            self.pause_duration_min = None
            self.pause_duration_max = None
            self.next_start_time = None
            if not self.remaining_minutes_list:
                self.remaining_minutes_list = list()
            if not self.planned_starts:
                self.planned_starts = list()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_appliance_type_display()}) - {self.house.name}"

    class Meta:
        verbose_name = "Spotřebič"
        verbose_name_plural = "Spotřebiče"

class ConsumptionData(models.Model):
    house = models.ForeignKey(
        House,
        on_delete=models.CASCADE,
        related_name='consumption_data',
        verbose_name="Dům"
    )
    date = models.DateField(verbose_name="Datum", default=date.today)
    time = models.CharField(max_length=5, verbose_name="Čas", default="00:00")
    appliance_consumption = models.JSONField(
        verbose_name="Spotřeba spotřebičů",
        help_text="Seznam ve formátu [{'appliance_id': 1, 'consumption_w': 100}, ...]"
    )
    
    class Meta:
        unique_together = ['house', 'date', 'time']  
        indexes = [
            models.Index(fields=['house', 'date', 'time']),
        ]
        ordering = ['date', 'time']
        verbose_name = "Spotřeba"
        verbose_name_plural = "Spotřeby"

    def clean(self):
        import re
        if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', self.time):
            from django.core.exceptions import ValidationError
            raise ValidationError({'time': 'Čas musí být ve formátu HH:MM (00:00-23:59)'})

    def __str__(self):
        total = sum(item['consumption_w'] for item in self.appliance_consumption)
        return f"{self.house.name} - {self.date} {self.time}: {total}W"