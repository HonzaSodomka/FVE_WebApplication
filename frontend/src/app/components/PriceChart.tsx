"use client";

import { useState, useEffect } from "react";
import { DatePicker } from "@/components/ui/date-picker";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
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
      return "#ef4444"; // červená
    case "medium":
      return "#f59e0b"; // oranžová
    case "low":
      return "#22c55e"; // zelená
    default:
      return "#gray";
  }
};

export default function PriceChart() {
  const [prices, setPrices] = useState<PriceData[]>([]);
  const [date, setDate] = useState<Date>(() => {
    const d = new Date();
    d.setFullYear(2025);
    return d;
  });
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const formattedDate = `${date.getFullYear()}-${String(
          date.getMonth() + 1
        ).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
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

  return (
    <div className="w-full space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Ceny elektřiny</h2>
        <DatePicker date={date} onSelect={setDate} />
      </div>

      {error ? (
        <Alert>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : (
        <div className="h-96 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="time"
                interval={0}
                angle={-45}
                textAnchor="end"
                height={60}
              />
              <YAxis
                label={{
                  value: "Cena (CZK)",
                  angle: -90,
                  position: "insideLeft",
                }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-white p-3 border rounded-lg shadow">
                        <p className="font-bold">{data.time}</p>
                        <p>Cena: {data.price_czk} Kč</p>
                        <p className="capitalize">Level: {data.level}</p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Bar
                dataKey="price_czk"
                fill="#2563eb"
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
                      rx={2}
                    />
                  );
                }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
