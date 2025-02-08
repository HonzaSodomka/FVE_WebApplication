"use client";

import React, { useState, useEffect } from "react";
import { format, isToday, parseISO } from "date-fns";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  TooltipProps,
} from "recharts";
import { Alert, AlertDescription } from "@/components/ui/alert";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ConsumptionData {
  hour: number;
  consumption_wh: number;
}

interface ChartData {
  time: string;
  consumption: number | null;
  isLive: boolean;
  hour: number;
}

interface ChartProps {
  houseId: number;
  date: Date;
}

export default function ConsumptionChart({ houseId, date }: ChartProps) {
  const [data, setData] = useState<ConsumptionData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [serverTime, setServerTime] = useState<Date | null>(null);
  const [dailyTotal, setDailyTotal] = useState<number>(0);

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
        if (jsonData.current_time) {
          setServerTime(parseISO(jsonData.current_time));
        }
        setData(jsonData.consumption);
        setDailyTotal(jsonData.daily_total || 0);
      } catch (err) {
        setError("Nepodařilo se načíst data o spotřebě");
        console.error(err);
      }
    };

    fetchData();

    if (isToday(date)) {
      const interval = setInterval(fetchData, 60000);
      return () => clearInterval(interval);
    }
  }, [houseId, date]);

  const chartData: ChartData[] = Array.from({ length: 24 }, (_, index) => {
    const displayHour = index + 1;
    const dataHour = index;
    const hourData = data.find(item => item.hour === dataHour);
    
    const isCurrentDay = isToday(date);
    const currentDisplayHour = serverTime ? serverTime.getHours() + 1 : 24;
    const isFutureHour = isCurrentDay && displayHour > currentDisplayHour;

    return {
      time: `${String(displayHour).padStart(2, "0")}:00`,
      consumption: isFutureHour ? null : (hourData?.consumption_wh || 0),
      isLive: serverTime ? displayHour === currentDisplayHour : false,
      hour: displayHour,
    };
  });

  const CustomTooltip = ({
    active,
    payload,
  }: TooltipProps<number, string>) => {
    if (active && payload && payload.length > 0 && payload[0].value !== null) {
      const value = payload[0].value as number;
      const data = payload[0].payload as ChartData;

      const startHour = data.hour - 1;
      const timeRange = `${String(startHour).padStart(2, "0")}:00 - ${String(startHour).padStart(2, "0")}:59`;

      return (
        <div className="bg-white p-3 border rounded-lg shadow">
          <p className="font-bold">{timeRange}</p>
          <p>
            Spotřeba: {value.toFixed(2)} Wh
            {data.isLive && (
              <span className="ml-2 text-green-600">(Live)</span>
            )}
          </p>
        </div>
      );
    }
    return null;
  };

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
          {isToday(date) && serverTime && (
            <span className="ml-2 text-sm bg-green-100 text-green-800 px-2 py-1 rounded-full">
              Live
            </span>
          )}
        </h2>
        <span className="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
          {format(date, "dd. MM. yyyy")}
        </span>
      </div>

      {/* Box s celkovou denní spotřebou */}
      <div className="text-center mb-4">
        <p className="text-sm text-gray-500">Celková denní spotřeba</p>
        <p className="text-xl font-bold text-blue-600">
          {dailyTotal.toFixed(2)} Wh
        </p>
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
                value: "Spotřeba (Wh)",
                angle: -90,
                position: "insideLeft",
                style: { fill: "#6B7280" },
              }}
            />
            <Tooltip content={CustomTooltip} />
            <Line
              type="monotone"
              dataKey="consumption"
              stroke="#3B82F6"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}