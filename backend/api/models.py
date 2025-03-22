"""
Datové modely pro aplikaci optimalizace nabíjení FVE baterie.

Tento modul definuje všechny datové entity používané v systému, včetně:
- Cenových dat elektřiny (PriceData)
- Predikce solární výroby (SolarData)
- Domů s FVE systémy (House)
- Spotřebičů v domácnosti (Appliance)
- Dat o spotřebě (ConsumptionData)
- Záznamů o nabíjení (ChargingData)
- Plánů nabíjení (ChargingSchedule)
"""

from django.db import models
from datetime import date
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import re


class PriceData(models.Model):
    """
    Model pro ukládání hodinových cenových dat elektřiny na spotovém trhu.
    """
    date = models.DateField()
    hour = models.IntegerField()
    price_czk = models.IntegerField()
    level = models.CharField(max_length=10)  # 'low', 'medium', 'high'
    level_num = models.IntegerField()

    class Meta:
        unique_together = ['date', 'hour']
        ordering = ['date', 'hour']

    def __str__(self):
        return f"{self.date} {self.hour}:00 - {self.price_czk} CZK ({self.level})"


class SolarData(models.Model):
    """
    Model pro ukládání dat o predikované solární výrobě.
    """
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
    """
    Model reprezentující dům s fotovoltaickým systémem.
    
    Obsahuje parametry solárního systému, baterie a nastavení rizikového profilu
    pro optimalizaci nabíjení.
    """
    RISK_LEVELS = [
        ('LOW', 'Nízké riziko'),       # Jistota energie za cenu vyšších nákladů
        ('MEDIUM', 'Střední riziko'),  # Vyvážený přístup
        ('HIGH', 'Vysoké riziko'),     # Agresivní optimalizace ceny s rizikem drahého dobíjení
        ('EXTREME', 'Extrémní riziko'),# Agresivní optimalizace s vypínáním spotřebičů
    ]

    # Základní informace
    name = models.CharField(max_length=100, verbose_name="Název domu")
    solar_power = models.FloatField(verbose_name="Výkon solárních panelů (kWp)")
    battery_capacity = models.FloatField(verbose_name="Kapacita baterie (kWh)")
    is_active = models.BooleanField(default=False, verbose_name="Aktivní simulace")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Solární variace pro simulaci reálných podmínek
    solar_variation = models.FloatField(
        default=1,
        verbose_name="Variace solární výroby"
    )
    
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
        default=0,
        verbose_name="Maximální nabíjecí výkon (kW)",
        help_text="Jak rychle lze baterii nabíjet"
    )
    max_discharging_power = models.FloatField(
        default=0,
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
    
    # Rizikový profil pro optimalizaci nabíjení
    risk_level = models.CharField(
        max_length=7,  # Změněno z 6 na 7 kvůli délce "EXTREME"
        choices=RISK_LEVELS,
        default='MEDIUM',
        verbose_name="Úroveň rizika",
        help_text="""
            NÍZKÉ: Nabíjí i za vyšší ceny pro zajištění dostatku energie
            STŘEDNÍ: Vyvážený přístup mezi cenou a jistotou energie
            VYSOKÉ: Riskantní optimalizace ceny, možnost nutnosti drahého dobíjení
            EXTRÉMNÍ: Maximální optimalizace ceny s vypínáním spotřebičů
        """
    )
    
    def __str__(self):
        return f"{self.name} ({self.solar_power} kWp, {self.battery_capacity} kWh)"
        
    class Meta:
        verbose_name = "Dům"
        verbose_name_plural = "Domy"
        

from django.db import models
from django.core.exceptions import ValidationError

class Appliance(models.Model):
    """
    Model reprezentující spotřebič v domácnosti.
    
    Systém podporuje čtyři typy spotřebičů:
    1. CONSTANT - konstantní spotřeba (např. router)
    2. CYCLIC - cyklický spotřebič střídající aktivní a standby režimy (např. lednice)
    3. SCHEDULED - plánovaný spotřebič spouštěný v definovaných časech (např. pračka)
    4. ON_DEMAND - spotřebič používaný náhodně podle pravděpodobnostního modelu (např. konvice)
    """
    APPLIANCE_TYPES = [
        ('CONSTANT', 'Konstantní spotřeba'),      # např. router
        ('CYCLIC', 'Cyklická spotřeba'),         # např. lednice
        ('SCHEDULED', 'Plánovaná spotřeba'),      # např. pračka
        ('ON_DEMAND', 'Spotřeba na vyžádání'),    # např. konvice
    ]
    
    # Priorita spotřebiče pro vypínání při optimalizaci
    PRIORITY_LEVELS = [
        (1, 'Kritický - nikdy nevypínat'),
        (2, 'Vysoká priorita - vypnout v krajní nouzi'),
        (3, 'Střední priorita - možné vypnout při vysokých cenách'),
        (4, 'Nízká priorita - vypnout jako první')
    ]
    
    # Základní pole
    house = models.ForeignKey(
        'House',
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
    appliance_type = models.CharField(
        max_length=20,
        choices=APPLIANCE_TYPES,
        verbose_name="Typ spotřebiče"
    )
    
    # Priorita spotřebiče pro vypínání
    priority_level = models.IntegerField(
        choices=PRIORITY_LEVELS,
        default=1,
        verbose_name="Priorita spotřebiče"
    )
    
    # Možnost přerušení běhu
    interruptible = models.BooleanField(
        default=False,  # Změněno z True na False
        verbose_name="Lze přerušit",
        help_text="Zda je možné přerušit běh spotřebiče uprostřed cyklu"
    )
    
    # Okna deaktivace pro CONSTANT a CYCLIC spotřebiče
    inactive_windows = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Okna deaktivace",
        help_text="Seznam časových oken, kdy je spotřebič vypnutý [{start_date: '2025-03-22', end_date: '2025-03-23', start_hour: 23, end_hour: 1}]"
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
        help_text="Seznam časových oken ve formátu [{start: int, end: int, probability: float, uses: int, is_active: bool}]"
    )
    weekend_hours = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Časová okna (víkend)",
        help_text="Seznam časových oken ve formátu [{start: int, end: int, probability: float, uses: int, is_active: bool}]"
    )

    def save(self, *args, **kwargs):
        """
        Přepisuje metodu save pro automatické nastavení polí podle typu spotřebiče
        a validaci povinných údajů.
        """
        # Validace standby_power podle typu spotřebiče
        if self.appliance_type == 'CYCLIC' and not self.standby_power:
            raise ValidationError('Pro cyklické spotřebiče je povinné vyplnit spotřebu v pohotovostním režimu')
        
        # Nastavení defaultních hodnot podle typu spotřebiče
        if self.appliance_type == 'CONSTANT':
            self._reset_and_set_constant_fields()
        elif self.appliance_type == 'CYCLIC':
            self._reset_and_set_cyclic_fields()
        elif self.appliance_type == 'SCHEDULED':
            self._reset_and_set_scheduled_fields()
        elif self.appliance_type == 'ON_DEMAND':
            self._reset_and_set_on_demand_fields()
            
        # Inicializace inactive_windows, pokud je None
        if self.inactive_windows is None:
            self.inactive_windows = []
            
        # Pro SCHEDULED a ON_DEMAND, zajistíme, že všechna časová okna mají is_active
        if self.appliance_type in ['SCHEDULED', 'ON_DEMAND']:
            if self.weekday_hours:
                for i, window in enumerate(self.weekday_hours):
                    if 'is_active' not in window:
                        self.weekday_hours[i]['is_active'] = True
                        
            if self.weekend_hours:
                for i, window in enumerate(self.weekend_hours):
                    if 'is_active' not in window:
                        self.weekend_hours[i]['is_active'] = True

        super().save(*args, **kwargs)
    
    def _reset_and_set_constant_fields(self):
        """Nastaví pole pro konstantní spotřebiče a zruší ostatní pole."""
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
    
    def _reset_and_set_cyclic_fields(self):
        """Nastaví pole pro cyklické spotřebiče a zruší ostatní pole."""
        self.is_active = None
        self.next_start_time = None
        self.planned_starts = None
        self.remaining_minutes_list = None
        self.usage_duration_min = None
        self.usage_duration_max = None
        self.weekday_hours = None
        self.weekend_hours = None
    
    def _reset_and_set_scheduled_fields(self):
        """Nastaví pole pro plánované spotřebiče a zruší ostatní pole."""
        self.in_standby = None
        self.remaining_minutes_list = None
        self.run_duration_min = None
        self.run_duration_max = None
        self.pause_duration_min = None
        self.pause_duration_max = None
        self.planned_starts = None
    
    def _reset_and_set_on_demand_fields(self):
        """Nastaví pole pro spotřebiče na vyžádání a zruší ostatní pole."""
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

    def __str__(self):
        return f"{self.name} ({self.get_appliance_type_display()}) - {self.house.name}"

    class Meta:
        verbose_name = "Spotřebič"
        verbose_name_plural = "Spotřebiče"


class ConsumptionData(models.Model):
    """
    Model pro ukládání minutových dat o spotřebě elektřiny v domě.
    
    Každý záznam obsahuje spotřebu jednotlivých spotřebičů v daném čase.
    """
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
        """Validuje formát času."""
        if not re.match(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$', self.time):
            raise ValidationError({'time': 'Čas musí být ve formátu HH:MM (00:00-23:59)'})

    def __str__(self):
        total = sum(item['consumption_w'] for item in self.appliance_consumption)
        return f"{self.house.name} - {self.date} {self.time}: {total}W"
    

class ChargingData(models.Model):
    """
    Model pro ukládání denních dat o nabíjení baterie.
    
    Sleduje množství energie nabyté ze solárů a ze sítě, 
    včetně nákladů na nabíjení ze sítě.
    """
    house = models.ForeignKey(
        House,
        on_delete=models.CASCADE,
        related_name='charging_data',
        verbose_name="Dům"
    )
    date = models.DateField(verbose_name="Datum", default=date.today)
    solar_charged_kwh = models.FloatField(
        verbose_name="Nabito ze solárů (kWh)",
        default=0
    )
    grid_charged_kwh = models.FloatField(
        verbose_name="Nabito ze sítě (kWh)",
        default=0
    )
    grid_charged_cost = models.FloatField(
        verbose_name="Cena nabíjení ze sítě (Kč)",
        default=0
    )

    class Meta:
        unique_together = ['house', 'date']
        indexes = [
            models.Index(fields=['house', 'date']),
        ]
        ordering = ['date']
        verbose_name = "Nabíjení"
        verbose_name_plural = "Nabíjení"

    def __str__(self):
        return f"{self.house.name} - {self.date}: Solar {self.solar_charged_kwh:.1f}kWh, Grid {self.grid_charged_kwh:.1f}kWh ({self.grid_charged_cost:.0f}Kč)"
    

class ChargingSchedule(models.Model):
    """
    Model pro ukládání plánu nabíjení baterie ze sítě.
    
    Každý záznam definuje množství energie, které má být nabito v konkrétní hodině daného dne.
    """
    house = models.ForeignKey(
        'House',
        on_delete=models.CASCADE,
        related_name='charging_schedules',
        verbose_name="Plán nabíjení"
    )
    date = models.DateField()
    hour = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)]
    )
    planned_charging_kwh = models.FloatField(
        validators=[MinValueValidator(0)]
    )

    class Meta:
        unique_together = ['house', 'date', 'hour']
        indexes = [
            models.Index(fields=['house', 'date', 'hour']),
        ]
        ordering = ['date', 'hour']