"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Power } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { format } from "date-fns";
import HouseDialog from "@/app/components/HouseDialog";
import ApplianceDialog from "@/app/components/ApplianceDialog";
import { Appliance } from "@/types/appliance";
import ConsumptionChart from "@/app/components/ConsumptionChart";
import { DatePicker } from "@/components/ui/date-picker";
import { Alert, AlertDescription } from "@/components/ui/alert";
import ApplianceList from "@/app/components/ApplianceList";
import ChargingScheduleChart from "@/app/components/ChargingScheduleChart";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface House {
  id: number;
  name: string;
  solar_power: number;
  battery_capacity: number;
  is_active: boolean;
  current_battery_level: number;
  min_battery_level: number;
  max_charging_power: number;
  max_discharging_power: number;
  charging_efficiency: number;
  discharging_efficiency: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
}

interface DailyStats {
  consumption_kwh: number;
  solar_charged_kwh: number;
  grid_charged_kwh: number;
  grid_charged_cost: number;
}

export default function Page() {
  const params = useParams();
  const [house, setHouse] = useState<House | null>(null);
  const [appliances, setAppliances] = useState<Appliance[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [date, setDate] = useState<Date>(new Date());
  const [isTogglingSimulation, setIsTogglingSimulation] = useState(false);
  const [dailyStats, setDailyStats] = useState<DailyStats>({
    consumption_kwh: 0,
    solar_charged_kwh: 0,
    grid_charged_kwh: 0,
    grid_charged_cost: 0,
  });

  const fetchDailyStats = useCallback(async () => {
    try {
      const [consumptionResponse, chargingResponse] = await Promise.all([
        fetch(
          `${API_URL}/api/houses/${params.id}/consumption/?date=${format(
            date,
            "yyyy-MM-dd"
          )}`,
          {
            credentials: "include",
          }
        ),
        fetch(
          `${API_URL}/api/houses/${params.id}/charging/?date=${format(
            date,
            "yyyy-MM-dd"
          )}`,
          {
            credentials: "include",
          }
        ),
      ]);

      const consumptionData = await consumptionResponse.json();
      const chargingData = await chargingResponse.json();

      setDailyStats({
        consumption_kwh: consumptionData.daily_total / 1000, // Převod z Wh na kWh
        solar_charged_kwh: chargingData.solar_charged_kwh,
        grid_charged_kwh: chargingData.grid_charged_kwh,
        grid_charged_cost: chargingData.grid_charged_cost,
      });
    } catch (err) {
      console.error("Failed to fetch daily stats:", err);
    }
  }, [params.id, date]);

  const fetchData = useCallback(async () => {
    try {
      const houseResponse = await fetch(`${API_URL}/api/houses/`, {
        credentials: "include",
      });
      const houseData = await houseResponse.json();
      const currentHouse = houseData.houses.find(
        (h: House) => h.id === parseInt(params.id as string)
      );

      if (!currentHouse) {
        throw new Error("Dům nenalezen");
      }

      setHouse(currentHouse);

      const appliancesResponse = await fetch(
        `${API_URL}/api/houses/${params.id}/appliances/`,
        {
          credentials: "include",
        }
      );
      const appliancesData = await appliancesResponse.json();

      setAppliances(appliancesData.appliances);
    } catch (err) {
      setError("Nepodařilo se načíst data");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [params.id]);

  const toggleSimulation = async () => {
    if (!house) return;

    try {
      setIsTogglingSimulation(true);
      const response = await fetch(
        `${API_URL}/api/houses/${params.id}/toggle_simulation/`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            is_active: !house.is_active,
          }),
        }
      );

      if (!response.ok) throw new Error("Nepodařilo se přepnout simulaci");

      await fetchData();
    } catch (err) {
      console.error(err);
      alert("Nepodařilo se přepnout simulaci");
    } finally {
      setIsTogglingSimulation(false);
    }
  };

  const handleDeleteAppliance = async (applianceId: number) => {
    if (window.confirm("Opravdu chcete smazat tento spotřebič?")) {
      try {
        const response = await fetch(
          `${API_URL}/api/houses/${params.id}/appliances/?id=${applianceId}`,
          { method: "DELETE", credentials: "include" }
        );

        if (!response.ok) throw new Error("Nepodařilo se smazat spotřebič");

        fetchData();
      } catch (err) {
        console.error(err);
        alert("Nepodařilo se smazat spotřebič");
      }
    }
  };

  useEffect(() => {
    if (params.id) {
      fetchData();
      fetchDailyStats();
    }
  }, [params.id, date, fetchData, fetchDailyStats]);

  if (isLoading) return <div className="text-center p-4">Načítání...</div>;
  if (error || !house)
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header sekce */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4 mb-6">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Link href="/houses">
                <Button variant="outline" size="icon">
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {house.name}
                </h1>
                <p className="text-sm text-gray-500 mt-1">
                  Instalovaný výkon: {house.solar_power} kWp | Kapacita baterie:{" "}
                  {house.battery_capacity} kWh
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <DatePicker date={date} onSelect={setDate} />
              <ApplianceDialog
                houseId={parseInt(params.id as string)}
                onSuccess={fetchData}
              />
            </div>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-12">
          {/* Levý sloupec */}
          <div className="col-span-12 lg:col-span-5 space-y-6">
            {/* Parametry domu */}
            <Card className="bg-white shadow-sm border border-gray-100">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xl font-semibold text-gray-900">
                  Parametry domu
                </CardTitle>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    className={`${
                      house.is_active
                        ? "text-green-500 hover:text-green-700 hover:bg-green-50"
                        : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                    }`}
                    onClick={toggleSimulation}
                    disabled={isTogglingSimulation}
                  >
                    {isTogglingSimulation ? (
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    ) : (
                      <Power className="h-4 w-4" />
                    )}
                  </Button>
                  <HouseDialog house={house} onSuccess={fetchData} />
                </div>
              </CardHeader>
              <CardContent>
                {/* Baterie */}
                <div className="bg-blue-50 rounded-lg p-4 mb-4">
                  <h3 className="text-sm font-medium text-blue-900 mb-3">
                    Stav baterie
                  </h3>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-blue-700">
                        Aktuální stav:
                      </span>
                      <span className="font-medium text-blue-900">
                        {Number(house.current_battery_level).toFixed(2)} kWh (
                        {(
                          (house.current_battery_level /
                            house.battery_capacity) *
                          100
                        ).toFixed(1)}
                        %)
                      </span>
                    </div>
                    <div className="w-full bg-blue-200 rounded-full h-2.5">
                      <div
                        className="bg-blue-600 h-2.5 rounded-full"
                        style={{
                          width: `${
                            (house.current_battery_level /
                              house.battery_capacity) *
                            100
                          }%`,
                        }}
                      ></div>
                    </div>
                    <div className="flex justify-between items-center text-sm text-blue-700">
                      <span>
                        Min:{" "}
                        {(
                          (house.min_battery_level / 100) *
                          house.battery_capacity
                        ).toFixed(1)}{" "}
                        kWh
                      </span>
                      <span>Max: {house.battery_capacity.toFixed(1)} kWh</span>
                    </div>
                  </div>
                </div>

                {/* Denní statistiky */}
                <div className="bg-green-50 rounded-lg p-4 mb-4">
                  <h3 className="text-sm font-medium text-green-900 mb-3">
                    Denní statistiky {format(date, "dd.MM.yyyy")}
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm flex justify-between">
                        <span className="text-green-600">Spotřeba:</span>
                        <span className="font-medium text-green-900">
                          {dailyStats.consumption_kwh.toFixed(2)} kWh
                        </span>
                      </p>
                      <p className="text-sm flex justify-between">
                        <span className="text-green-600">
                          Nabito ze solárů:
                        </span>
                        <span className="font-medium text-green-900">
                          {dailyStats.solar_charged_kwh.toFixed(2)} kWh
                        </span>
                      </p>
                    </div>
                    <div>
                      <p className="text-sm flex justify-between">
                        <span className="text-green-600">Nabito ze sítě:</span>
                        <span className="font-medium text-green-900">
                          {dailyStats.grid_charged_kwh.toFixed(2)} kWh
                        </span>
                      </p>
                      <p className="text-sm flex justify-between">
                        <span className="text-green-600">Cena nabíjení:</span>
                        <span className="font-medium text-green-900">
                          {dailyStats.grid_charged_cost.toFixed(2)} Kč
                        </span>
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  {/* Výkonové parametry */}
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h3 className="text-sm font-medium text-gray-900 mb-2">
                      Výkonové parametry
                    </h3>
                    <div className="space-y-2">
                      <p className="text-sm flex justify-between">
                        <span className="text-gray-600">Nabíjecí výkon:</span>
                        <span className="font-medium text-gray-900">
                          {house.max_charging_power} kW
                        </span>
                      </p>
                      <p className="text-sm flex justify-between">
                        <span className="text-gray-600">Vybíjecí výkon:</span>
                        <span className="font-medium text-gray-900">
                          {house.max_discharging_power} kW
                        </span>
                      </p>
                    </div>
                  </div>

                  {/* Účinnost */}
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h3 className="text-sm font-medium text-gray-900 mb-2">
                      Účinnost
                    </h3>
                    <div className="space-y-2">
                      <p className="text-sm flex justify-between">
                        <span className="text-gray-600">Nabíjení:</span>
                        <span className="font-medium text-gray-900">
                          {house.charging_efficiency}%
                        </span>
                      </p>
                      <p className="text-sm flex justify-between">
                        <span className="text-gray-600">Vybíjení:</span>
                        <span className="font-medium text-gray-900">
                          {house.discharging_efficiency}%
                        </span>
                      </p>
                    </div>
                  </div>

                  {/* Risk level a status */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h3 className="text-sm font-medium text-gray-900 mb-2">
                        Úroveň rizika
                      </h3>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          {
                            LOW: "bg-green-100 text-green-800",
                            MEDIUM: "bg-yellow-100 text-yellow-800",
                            HIGH: "bg-red-100 text-red-800",
                          }[house.risk_level]
                        }`}
                      >
                        {
                          {
                            LOW: "Nízká - bezpečnější nabíjení",
                            MEDIUM: "Střední - vyvážený přístup",
                            HIGH: "Vysoká - agresivní optimalizace",
                          }[house.risk_level]
                        }
                      </span>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h3 className="text-sm font-medium text-gray-900 mb-2">
                        Status simulace
                      </h3>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          house.is_active
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {house.is_active ? "Simulace běží" : "Simulace zastavena"}
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Spotřebiče */}
            <ApplianceList 
              appliances={appliances}
              houseId={parseInt(params.id as string)}
              onSuccess={fetchData}
              onDelete={handleDeleteAppliance}
            />
          </div>

          {/* Pravý sloupec - grafy */}
          <div className="col-span-12 lg:col-span-7 space-y-6">
            {/* Plánované nabíjení */}
            <ChargingScheduleChart
              houseId={parseInt(params.id as string)}
              date={date}
            />

            {/* Graf spotřeby */}
            <Card className="bg-white shadow-sm border border-gray-100">
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-xl font-semibold text-gray-900">
                  Spotřeba energie
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ConsumptionChart
                  houseId={parseInt(params.id as string)}
                  date={date}
                />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </main>
  );
}