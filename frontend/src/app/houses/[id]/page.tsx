"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import HouseDialog from "@/app/components/HouseDialog";
import ApplianceDialog from "@/app/components/ApplianceDialog";
import { TimeWindow } from "@/types/appliance";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface House {
  id: number;
  name: string;
  solar_power: number;
  battery_capacity: number;
}

interface ApiAppliance {
  id: number;
  name: string;
  power_consumption: number;
  appliance_type: "CONSTANT" | "CYCLIC" | "SCHEDULED" | "ON_DEMAND";
  run_duration_min?: number;
  run_duration_max?: number;
  pause_duration_min?: number;
  pause_duration_max?: number;
  usage_duration_min?: number;
  usage_duration_max?: number;
  uses_per_window?: number;
  weekday_hours: number[][];
  weekend_hours: number[][];
}

interface Appliance
  extends Omit<ApiAppliance, "weekday_hours" | "weekend_hours"> {
  weekday_hours: TimeWindow[];
  weekend_hours: TimeWindow[];
}

export default function Page() {
  const params = useParams();
  const [house, setHouse] = useState<House | null>(null);
  const [appliances, setAppliances] = useState<Appliance[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const transformOldToNewFormat = (windows: number[][]): TimeWindow[] => {
    return windows.map((window) => ({
      start: window[0],
      end: window[1],
      probability: 1.0,
    }));
  };

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

      // Transformace starého formátu na nový
      const transformedAppliances = appliancesData.appliances.map(
        (appliance: ApiAppliance) => ({
          ...appliance,
          weekday_hours: transformOldToNewFormat(appliance.weekday_hours),
          weekend_hours: transformOldToNewFormat(appliance.weekend_hours),
        })
      );

      setAppliances(transformedAppliances);
    } catch (err) {
      setError("Nepodařilo se načíst data");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [params.id]);

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
    }
  }, [params.id, fetchData]);

  if (isLoading) return <div className="text-center p-4">Načítání...</div>;
  if (error || !house) return <div className="text-red-500 p-4">{error}</div>;

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <Link href="/houses">
              <Button variant="outline" size="icon" className="mr-4">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-2xl font-bold">{house.name}</h1>
          </div>
          <ApplianceDialog
            houseId={parseInt(params.id as string)}
            onSuccess={fetchData}
          />
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>Parametry domu</CardTitle>
              <HouseDialog house={house} onSuccess={fetchData} />
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <p className="text-gray-600">
                  Solární panely: {house.solar_power} kWp
                </p>
                <p className="text-gray-600">
                  Kapacita baterie: {house.battery_capacity} kWh
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Spotřebiče</CardTitle>
            </CardHeader>
            <CardContent>
              {appliances.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  Zatím nejsou přidány žádné spotřebiče
                </div>
              ) : (
                <div className="space-y-4">
                  {appliances.map((appliance) => (
                    <div
                      key={appliance.id}
                      className="p-4 border rounded-lg hover:bg-gray-50"
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <h3 className="font-medium">{appliance.name}</h3>
                          <p className="text-sm text-gray-600">
                            Spotřeba: {appliance.power_consumption} W
                          </p>
                          <p className="text-sm text-gray-600">
                            Typ: {appliance.appliance_type}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <ApplianceDialog
                            houseId={parseInt(params.id as string)}
                            appliance={appliance}
                            onSuccess={fetchData}
                          />
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-red-500 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDeleteAppliance(appliance.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
