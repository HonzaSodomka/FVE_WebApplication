"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
} from "recharts";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface SolarData {
  timestamp: string;
  watts: number;
  watt_hours_period: number;
  watt_hours_cumulative: number;
}

interface ChartData {
  hour: string;
  watts: number;
  wattHoursPeriod: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SolarDataChart({ date }: { date: Date }) {
  const [solarData, setSolarData] = useState<ChartData[]>([]);
  const [error, setError] = useState<string>("");
  const [dailyTotal, setDailyTotal] = useState<number>(0);

  useEffect(() => {
    const fetchSolarData = async () => {
      try {
        const formattedDate = format(date, "yyyy-MM-dd");
        const response = await fetch(
          `${API_URL}/api/solar_prediction/?date=${formattedDate}`
        );
        const data = await response.json();

        if (data.predictions.length === 0) {
          setError(`Pro datum ${formattedDate} nejsou k dispozici žádná data.`);
          setSolarData([]);
          setDailyTotal(0);
        } else {
          setError("");

          const processedData = Array(24)
            .fill(null)
            .map((_, index) => ({
              hour: `${String(index).padStart(2, "0")}:00`,
              watts: 0,
              wattHoursPeriod: 0,
            }));

          data.predictions.forEach((item: SolarData) => {
            const hour = new Date(item.timestamp).getHours();
            processedData[hour] = {
              hour: `${String(hour).padStart(2, "0")}:00`,
              watts: item.watts / 1000,
              wattHoursPeriod: item.watt_hours_period / 1000,
            };
          });

          setSolarData(processedData);
          setDailyTotal(data.daily_total / 1000);
        }
      } catch (err) {
        setError("Nepodařilo se načíst solární data");
        console.error(err);
      }
    };

    fetchSolarData();
  }, [date]);

  return (
    <div className="space-y-6 bg-white p-6 rounded-xl shadow-lg border border-gray-200">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800 mb-4 flex items-center">
          <svg
            className="w-6 h-6 mr-2 text-green-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
            />
          </svg>
          Predikce výroby z FVE
        </h2>
        <span className="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
          {format(date, "dd. MM. yyyy")}
        </span>
      </div>
      <div className="text-center mb-4">
        <p className="text-sm text-gray-500">Celková denní produkce</p>
        <p className="text-xl font-bold text-green-600">
          {dailyTotal.toFixed(2)} kWh
        </p>
      </div>
      {error ? (
        <Alert
          variant="destructive"
          className="bg-red-50 border-red-200 text-red-700"
        >
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={solarData}
              margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(156, 163, 175, 0.2)"
              />
              <XAxis
                dataKey="hour"
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
                        <p className="font-bold">{data.hour}</p>
                        <p>Výkon: {data.watts.toFixed(2)} kW</p>
                        <p>
                          Vyrobená energie: {data.wattHoursPeriod.toFixed(2)}{" "}
                          kWh
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Area
                type="monotone"
                dataKey="wattHoursPeriod"
                stroke="rgba(16, 185, 129, 0.8)"
                fill="rgba(16, 185, 129, 0.1)"
              />
              <Line
                type="monotone"
                dataKey="wattHoursPeriod"
                stroke="rgba(16, 185, 129, 0.8)"
                strokeWidth={2}
                dot={{ r: 3, fill: "#10B981" }}
                activeDot={{ r: 5, fill: "#10B981" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {!error && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg space-y-2 text-sm text-gray-600">
          <h3 className="font-semibold text-gray-700">
            Parametry FVE systému:
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p>Lokalita: TUL budova A</p>
              <p>Zeměpisná šířka: 50.7728417°</p>
              <p>Zeměpisná délka: 15.0721458°</p>
            </div>
            <div>
              <p>Sklon panelů: 30°</p>
              <p>Azimut: 0° (orientace na jih)</p>
              <p>Instalovaný výkon: 20 kWp</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
