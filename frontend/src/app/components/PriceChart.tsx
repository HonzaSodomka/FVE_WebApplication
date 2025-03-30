"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Alert, AlertDescription } from "@/components/ui/alert";

//Pro type checking při vývoji - interfaces
interface PriceData {
  hour: number;
  price_czk: number;
  level: string;
  level_num: number;
}

interface BarProps {
  x: number;
  y: number;
  width: number;
  height: number;
  fill: string;
  payload: {
    hour: number;
    price_czk: number;
    level: string;
    level_num: number;
    time: string;
    color: string;
    price_czk_kwh: number;
    display_level: string;
  };
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const getLevelColor = (level: string) => {
  switch (level) {
    case "high":
      return "rgba(239, 68, 68, 0.8)";
    case "medium":
      return "rgba(245, 158, 11, 0.8)";
    case "low":
      return "rgba(34, 197, 94, 0.8)";
    case "negative":
      return "rgba(59, 130, 246, 0.8)"; // Modrá barva pro záporné ceny
    default:
      return "rgba(107, 114, 128, 0.8)";
  }
};

export default function PriceChart({ date }: { date: Date }) {
  const [prices, setPrices] = useState<PriceData[]>([]);
  const [error, setError] = useState<string>("");
  // Používáme přesnou definici typu pro doménu YAxis
  const [yAxisDomain, setYAxisDomain] = useState<[number, "auto"]>([0, "auto"]);

  //Načítá data při změně datumu
  useEffect(() => {
    const fetchPrices = async () => {
      try {
        //Naformátuje datum a zeptá se api jestli existuje záznam pro něj
        const formattedDate = format(date, "yyyy-MM-dd");
        const response = await fetch(
          `${API_URL}/api/prices/?date=${formattedDate}`,
          {
            credentials: "include",
          }
        );

        const data = await response.json();

        // Kontrola response status kódu
        if (!response.ok) {
          // Backend teď vrací chybovou zprávu v data.error
          setError(
            data.error ||
              `Pro datum ${formattedDate} nepodařilo se načíst data.`
          );
          setPrices([]);
          return;
        }

        //Pokud je záznam seřadí data podle hodin a nastaví je
        setError("");
        const sortedPrices = data.prices.sort(
          (a: PriceData, b: PriceData) => a.hour - b.hour
        );
        setPrices(sortedPrices);

        // Najít minimální a maximální cenu pro nastavení Y osy
        const minPrice = Math.min(
          ...sortedPrices.map((price: PriceData) => price.price_czk / 1000)
        );
        const hasNegativePrices = minPrice < 0;

        if (hasNegativePrices) {
          // Pokud máme záporné ceny, nastavíme spodní limit Y osy
          // na zaokrouhlení minima dolů (aby se zobrazil prostor pod zápornou cenou)
          const minYAxis = Math.floor(minPrice) - 0.2;
          setYAxisDomain([minYAxis, "auto"] as [number, "auto"]);
        } else {
          // Pokud nemáme záporné ceny, začínáme od 0
          setYAxisDomain([0, "auto"] as [number, "auto"]);
        }
      } catch (err) {
        setError("Nepodařilo se načíst data");
        console.error(err);
      }
    };

    fetchPrices();
  }, [date]);

  // Nastavuje data pro tabulku - nastavení hodiny, barvy a přepočet z ceny za MWh na kWh
  const chartData = prices.map((price) => {
    // Přidáme speciální level pro záporné ceny
    const level = price.price_czk < 0 ? "negative" : price.level;

    return {
      ...price,
      time: `${String(price.hour).padStart(2, "0")}:00`,
      color: getLevelColor(level),
      price_czk_kwh: price.price_czk / 1000,
      // Přidáme upravený level pro záporné ceny
      display_level: level,
    };
  });

  // Průměrná cena také přepočtena na kWh
  const averagePrice =
    prices.length > 0
      ? prices.reduce((sum, price) => sum + price.price_czk, 0) /
        prices.length /
        1000
      : 0;

  return (
    <div className="space-y-6 bg-white p-6 rounded-xl shadow-lg border border-gray-200">
      {/* Header s nadpisem a datem */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800 mb-4 flex items-center">
          <svg
            className="w-6 h-6 mr-2 text-yellow-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
          Ceny elektřiny
        </h2>
        <span className="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
          {format(date, "dd. MM. yyyy")}
        </span>
      </div>

      {/* Zobrazení chyby nebo obsahu */}
      {error ? (
        <Alert
          variant="destructive"
          className="bg-red-50 border-red-200 text-red-700"
        >
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : (
        <>
          {/* Box s průměrnou cenou */}
          <div className="text-center mb-4">
            <p className="text-sm text-gray-500">Průměrná cena</p>
            <p className="text-xl font-bold text-blue-600">
              {averagePrice.toFixed(2)} Kč/kWh
            </p>
          </div>

          {/* Graf */}
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(156, 163, 175, 0.2)"
                />
                <XAxis
                  dataKey="time"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#6B7280", fontSize: 12 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#6B7280", fontSize: 12 }}
                  domain={yAxisDomain as [number, string]}
                />
                {/* Přidáme referenční linii pro nulu, aby byl jasný rozdíl mezi kladnými a zápornými cenami */}
                <ReferenceLine y={0} stroke="#888" strokeDasharray="3 3" />
                {/* Referenční linie pro průměrnou cenu */}
                <ReferenceLine
                  y={averagePrice}
                  stroke="#3B82F6"
                  strokeDasharray="3 3"
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-white p-3 border rounded-lg shadow">
                          <p className="font-bold">{data.time}</p>
                          <p>Cena: {data.price_czk_kwh.toFixed(2)} Kč/kWh</p>
                          <p>
                            Úroveň:{" "}
                            {data.display_level === "negative"
                              ? "Záporná"
                              : data.display_level.charAt(0).toUpperCase() +
                                data.display_level.slice(1)}
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar
                  dataKey="price_czk_kwh"
                  shape={(props: unknown) => {
                    const { x, y, width, height, payload } = props as BarProps;

                    // Pro záporné ceny musíme upravit pozici a výšku sloupce
                    const isNegative = payload.price_czk_kwh < 0;
                    const barHeight = Math.abs(height);

                    // Opraveno: Pro záporné hodnoty potřebujeme ZAČÍT OD NULOVÉ OSY
                    // Najdeme pozici nulové osy v souřadnicovém systému grafu
                    // Recharts už poskytuje tuto informaci jako část návrhu grafu
                    const zeroY = y + height; // Pro záporné hodnoty, výška je záporná, takže přidáváme

                    const barY = isNegative ? zeroY : y;

                    return (
                      <rect
                        x={x}
                        y={barY}
                        width={width}
                        height={barHeight}
                        fill={payload.color}
                        rx={4}
                        ry={4}
                      />
                    );
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
