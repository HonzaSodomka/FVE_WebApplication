"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Trash2 } from "lucide-react";
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
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8 bg-white p-6 rounded-lg shadow-lg">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Link href="/">
                <Button variant="outline" size="icon">
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </Link>
              <h1 className="text-2xl font-bold">Správa domů</h1>
            </div>
            <HouseDialog onSuccess={fetchHouses} />
          </div>
        </header>

        <section className="bg-white rounded-lg shadow-lg p-6">
          {isLoading ? (
            <div className="text-center text-gray-500 py-8">Načítání...</div>
          ) : error ? (
            <div className="text-center text-red-500 py-8">{error}</div>
          ) : houses.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              Zatím nejsou přidány žádné domy
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {houses.map((house) => (
                <Card key={house.id}>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0">
                    <CardTitle>{house.name}</CardTitle>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-red-500 hover:text-red-700 hover:bg-red-50"
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
                    <div className="space-y-2">
                      <p className="text-gray-600">
                        Solární panely: {house.solar_power} kWp
                      </p>
                      <p className="text-gray-600">
                        Kapacita baterie: {house.battery_capacity} kWh
                      </p>
                    </div>
                  </CardContent>
                  <div className="p-6 pt-0 flex justify-end">
                    <Button
                      variant="default"
                      className="bg-gray-900 hover:bg-gray-700"
                      onClick={() => router.push(`/houses/${house.id}`)}
                    >
                      Detail domu
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
