"use client";

import React, { useState, useEffect } from "react";
import { format } from "date-fns";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Alert, AlertDescription } from "@/components/ui/alert";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ConsumptionData {
  timestamp: string;
  appliances: {
    appliance_id: number;
    consumption_w: number;
  }[];
}

interface ChartProps {
  houseId: number;
  date: Date;
}

export default function ConsumptionChart({ houseId, date }: ChartProps) {
  const [data, setData] = useState<ConsumptionData[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const formattedDate = format(date, "yyyy-MM-dd");
        const response = await fetch(
          `${API_URL}/api/houses/${houseId}/consumption/?date=${formattedDate}`,
          {
            credentials: "include",
          }
        );

        if (!response.ok) {
          throw new Error("Nepodařilo se načíst data o spotřebě");
        }

        const jsonData = await response.json();
        setData(jsonData.consumption);
      } catch (err) {
        setError("Nepodařilo se načíst data o spotřebě");
        console.error(err);
      }
    };

    fetchData();
  }, [houseId, date]);

  // Převedení dat do formátu pro graf
  const chartData = data.map((item) => ({
    time: format(new Date(item.timestamp), "HH:mm"),
    consumption: item.appliances.reduce(
      (sum, appliance) => sum + appliance.consumption_w,
      0
    ),
  }));

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6 bg-white p-6 rounded-xl shadow-lg border border-gray-200">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800 mb-4 flex items-center">
          <svg
            className="w-6 h-6 mr-2 text-blue-500"
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
          Spotřeba elektřiny
        </h2>
        <span className="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
          {format(date, "dd. MM. yyyy")}
        </span>
      </div>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="time"
              tick={{ fill: "#6B7280", fontSize: 12 }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: "#6B7280", fontSize: 12 }}
              label={{
                value: "Spotřeba (W)",
                angle: -90,
                position: "insideLeft",
                style: { fill: "#6B7280" },
              }}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (
                  active &&
                  payload &&
                  payload.length &&
                  payload[0]?.value !== undefined
                ) {
                  // Přidej bezpečnostní kontroly
                  const value = payload[0].value;
                  const formattedValue = Array.isArray(value)
                    ? parseFloat(value[0] as string).toFixed(2)
                    : typeof value === "number"
                    ? value.toFixed(2)
                    : parseFloat(value).toFixed(2);

                  return (
                    <div className="bg-white p-3 border rounded-lg shadow">
                      <p className="font-bold">{label}</p>
                      <p>Spotřeba: {formattedValue} W</p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Line
              type="monotone"
              dataKey="consumption"
              stroke="#3B82F6"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
