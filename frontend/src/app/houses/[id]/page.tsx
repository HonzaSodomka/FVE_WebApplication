"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Plus } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import HouseDialog from "@/app/components/HouseDialog";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface House {
  id: number;
  name: string;
  solar_power: number;
  battery_capacity: number;
}

export default function Page() {
  const params = useParams();
  const [house, setHouse] = useState<House | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/houses/`);
      const data = await response.json();
      const currentHouse = data.houses.find(
        (h: House) => h.id === parseInt(params.id as string)
      );

      if (!currentHouse) {
        throw new Error("Dům nenalezen");
      }

      setHouse(currentHouse);
    } catch (err) {
      setError("Nepodařilo se načíst data");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [params.id]);

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
        {/* Header s navigací a tlačítkem pro přidání */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <Link href="/houses">
              <Button variant="outline" size="icon" className="mr-4">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-2xl font-bold">{house.name}</h1>
          </div>
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Přidat spotřebič
          </Button>
        </div>

        {/* Grid s informacemi o domě a spotřebiči */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Karta s informacemi o domě */}
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

          {/* Karta se spotřebiči */}
          <Card>
            <CardHeader>
              <CardTitle>Spotřebiče</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center text-gray-500 py-8">
                Zatím nejsou přidány žádné spotřebiče
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
