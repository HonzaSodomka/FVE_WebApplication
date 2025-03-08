import React, { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  TooltipProps
} from 'recharts';
import { Alert, AlertDescription } from "@/components/ui/alert";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChargingScheduleProps {
  houseId: number;
  date: Date;
}

interface ScheduleData {
  hour: number;
  planned_charging_kwh: number;
  time: string;
}

interface PriceData {
  hour: number;
  price_czk: number;
  level: string;
  level_num: number;
}

// Helper funkce pro formátování data jako YYYY-MM-DD
function formatDateForAPI(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Helper funkce pro formátování data jako DD. MM. YYYY
function formatDisplayDate(date: Date): string {
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  return `${day}. ${month}. ${year}`;
}

export default function ChargingScheduleChart({ houseId, date }: ChargingScheduleProps) {
  const [scheduleData, setScheduleData] = useState<ScheduleData[]>([]);
  const [priceData, setPriceData] = useState<PriceData[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      setMessage(null);
      
      try {
        const formattedDate = formatDateForAPI(date);
        
        // Načtení dat o nabíjecím plánu
        const response = await fetch(
          `${API_URL}/api/houses/${houseId}/charging_schedule/?date=${formattedDate}`,
          {
            credentials: "include",
          }
        );

        if (!response.ok) {
          throw new Error("Nepodařilo se načíst data o plánovaném nabíjení");
        }

        const data = await response.json();
        
        // Nastavení zprávy z API, pokud existuje
        if (data.message) {
          setMessage(data.message);
        }
        
        // Formátování dat pro graf
        const formattedData = data.schedule.map((item: any) => ({
          hour: item.hour,
          planned_charging_kwh: parseFloat(item.planned_charging_kwh),
          time: `${String(item.hour).padStart(2, "0")}:00`,
        }));
        
        setScheduleData(formattedData);
        
        // Načtení dat o cenách pro kontext
        const priceResponse = await fetch(
          `${API_URL}/api/prices/?date=${formattedDate}`,
          {
            credentials: "include",
          }
        );
        
        if (priceResponse.ok) {
          const priceData = await priceResponse.json();
          setPriceData(priceData.prices || []);
        }
        
      } catch (err) {
        console.error("Error fetching charging schedule:", err);
        setError("Nepodařilo se načíst data o plánovaném nabíjení");
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [houseId, date]);

  // Custom tooltip pro graf
  const CustomTooltip = ({ active, payload, label }: TooltipProps<number, string>) => {
    if (active && payload && payload.length) {
      const hourData = payload[0].payload as ScheduleData;
      const priceInfo = priceData.find(p => p.hour === hourData.hour);
      
      return (
        <div className="bg-white p-3 border rounded-lg shadow-lg">
          <p className="font-bold">{hourData.time}</p>
          <p>
            Plánované nabíjení: {hourData.planned_charging_kwh.toFixed(2)} kWh
          </p>
          {priceInfo && (
            <>
              <p>Cena: {(priceInfo.price_czk / 1000).toFixed(2)} Kč/kWh</p>
              <p>Kategorie: {
                priceInfo.level === "low" ? "Nízká" :
                priceInfo.level === "medium" ? "Střední" :
                priceInfo.level === "high" ? "Vysoká" : "Neznámá"
              }</p>
            </>
          )}
        </div>
      );
    }
    return null;
  };

  if (isLoading) {
    return <div className="p-6 flex justify-center items-center">Načítání dat...</div>;
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  // Zobrazení informativní zprávy, pokud není plán nabíjení
  if (scheduleData.length === 0) {
    return (
      <div className="bg-gray-50 rounded-lg p-6 text-center border border-gray-200">
        <p className="text-gray-600">{message || "Pro tento den není naplánováno žádné nabíjení ze sítě."}</p>
      </div>
    );
  }

  // Výpočet celkového plánovaného nabíjení
  const totalPlannedCharging = scheduleData.reduce(
    (sum, item) => sum + item.planned_charging_kwh, 
    0
  );

  return (
    <div className="space-y-4 bg-white p-6 rounded-xl shadow-lg border border-gray-200">
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
          Plánované nabíjení ze sítě
        </h2>
        <span className="text-sm font-medium text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
          {formatDisplayDate(date)}
        </span>
      </div>

      <div className="text-center mb-4">
        <p className="text-sm text-gray-500">Celkové plánované nabíjení</p>
        <p className="text-xl font-bold text-blue-600">
          {totalPlannedCharging.toFixed(2)} kWh
        </p>
      </div>

      <div className="h-80 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={scheduleData}
            margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="time" 
              tick={{ fill: "#6B7280", fontSize: 12 }}
            />
            <YAxis 
              tick={{ fill: "#6B7280", fontSize: 12 }}
              label={{ 
                value: "Nabíjení (kWh)", 
                angle: -90, 
                position: "insideLeft",
                style: { fill: "#6B7280" }
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Bar 
              name="Plánované nabíjení (kWh)"
              dataKey="planned_charging_kwh" 
              fill="#3B82F6"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      
      <div className="mt-4 text-sm text-gray-500 bg-gray-50 p-4 rounded-lg">
        <p>Graf zobrazuje plánované nabíjení baterie ze sítě na základě optimalizace podle spotových cen elektřiny. Nabíjení ze solárních panelů není v grafu zahrnuto.</p>
      </div>
    </div>
  );
}