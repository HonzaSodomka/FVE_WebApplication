"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Trash2, ArrowRight, Home, SunMedium, Battery } from "lucide-react";
import { useRouter } from "next/navigation";
import HouseDialog from "@/app/components/HouseDialog";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface House {
  id: number;
  name: string;
  solar_power: number;
  battery_capacity: number;
}

export default function Page() {
  const router = useRouter();
  const [houses, setHouses] = useState<House[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHouses = async () => {
    try {
      const response = await fetch(`${API_URL}/api/houses/`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("Nepodařilo se načíst data");
      const data = await response.json();
      setHouses(data.houses);
    } catch (err) {
      setError("Nepodařilo se načíst domy");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHouses();
  }, []);

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8 bg-white p-6 rounded-lg shadow-sm border border-gray-100">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Link href="/">
                <Button variant="outline" size="icon">
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Správa domů</h1>
                <p className="text-sm text-gray-500 mt-1">
                  Celkem domů: {houses.length}
                </p>
              </div>
            </div>
            <HouseDialog onSuccess={fetchHouses} />
          </div>
        </header>

        <section className="bg-white rounded-lg shadow-sm border border-gray-100 p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            </div>
          ) : error ? (
            <div className="bg-red-50 text-red-600 rounded-lg p-4 text-center">
              {error}
            </div>
          ) : houses.length === 0 ? (
            <div className="text-center py-12">
              <Home className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Žádné domy</h3>
              <p className="text-gray-500 mb-6">
                Zatím zde nejsou přidány žádné domy k monitorování
              </p>
              <HouseDialog onSuccess={fetchHouses} />
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {houses.map((house) => (
                <Card 
                  key={house.id}
                  className="group hover:shadow-md transition-all duration-200 border border-gray-100"
                >
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <div className="flex items-center gap-2">
                      <Home className="h-5 w-5 text-gray-400" />
                      <CardTitle>{house.name}</CardTitle>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 hover:bg-red-50 transition-opacity"
                      onClick={async () => {
                        if (
                          window.confirm("Opravdu chcete smazat tento dům?")
                        ) {
                          try {
                            const response = await fetch(
                              `${API_URL}/api/houses/?id=${house.id}`,
                              { 
                                method: "DELETE",
                                credentials: "include"
                              }
                            );

                            if (!response.ok)
                              throw new Error("Nepodařilo se smazat dům");

                            fetchHouses();
                          } catch (err) {
                            console.error(err);
                            alert("Nepodařilo se smazat dům");
                          }
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4 py-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-yellow-50 rounded-lg">
                          <SunMedium className="h-5 w-5 text-yellow-600" />
                        </div>
                        <div>
                          <p className="text-sm text-gray-500">Solární panely</p>
                          <p className="font-medium text-gray-900">{house.solar_power} kWp</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-50 rounded-lg">
                          <Battery className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="text-sm text-gray-500">Kapacita baterie</p>
                          <p className="font-medium text-gray-900">{house.battery_capacity} kWh</p>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                  <div className="p-4 border-t bg-gray-50">
                    <Button
                      variant="default"
                      className="w-full bg-gray-900 hover:bg-gray-800 text-white gap-2"
                      onClick={() => router.push(`/houses/${house.id}`)}
                    >
                      Detail domu
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}