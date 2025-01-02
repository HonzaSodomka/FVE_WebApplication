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
    default:
      return "rgba(107, 114, 128, 0.8)";
  }
};

export default function PriceChart({ date }: { date: Date }) {
  const [prices, setPrices] = useState<PriceData[]>([]);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const formattedDate = format(date, "yyyy-MM-dd");
        const response = await fetch(
          `${API_URL}/api/prices/?date=${formattedDate}`
        );
        const data = await response.json();

        if (data.prices.length === 0) {
          setError(`Pro datum ${formattedDate} nejsou k dispozici žádná data.`);
          setPrices([]);
        } else {
          setError("");
          setPrices(
            data.prices.sort((a: PriceData, b: PriceData) => a.hour - b.hour)
          );
        }
      } catch (err) {
        setError("Nepodařilo se načíst data");
        console.error(err);
      }
    };

    fetchPrices();
  }, [date]);

  const chartData = prices.map((price) => ({
    ...price,
    time: `${String(price.hour).padStart(2, "0")}:00`,
    color: getLevelColor(price.level),
  }));

  const averagePrice =
    prices.reduce((sum, price) => sum + price.price_czk, 0) / prices.length;

  return (
    <div className="space-y-6 bg-white p-6 rounded-xl shadow-lg border border-gray-200">
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
      {error ? (
        <Alert
          variant="destructive"
          className="bg-red-50 border-red-200 text-red-700"
        >
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : (
        <>
          <div className="text-center mb-4">
            <p className="text-sm text-gray-500">Průměrná cena</p>
            <p className="text-xl font-bold text-blue-600">
              {averagePrice.toFixed(2)} Kč/kWh
            </p>
          </div>
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
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-white p-3 border rounded-lg shadow">
                          <p className="font-bold">{data.time}</p>
                          <p>Cena: {data.price_czk} Kč/kWh</p>
                          <p className="capitalize">Úroveň: {data.level}</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <ReferenceLine
                  y={averagePrice}
                  stroke="#3B82F6"
                  strokeDasharray="3 3"
                />
                <Bar
                  dataKey="price_czk"
                  shape={(props: unknown) => {
                    const { x, y, width, height, payload } = props as BarProps;
                    return (
                      <rect
                        x={x}
                        y={y}
                        width={width}
                        height={height}
                        fill={getLevelColor(
                          (payload as BarProps["payload"]).level
                        )}
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
