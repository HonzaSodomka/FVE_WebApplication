import React, { useState, useEffect } from 'react';
import { Alert, AlertDescription } from "@/components/ui/alert";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChargingScheduleProps {
  houseId: number;
  date: Date;
}

interface ScheduleItem {
  hour: number;
  planned_charging_kwh: string | number;
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

export default function ChargingScheduleDisplay({ houseId, date }: ChargingScheduleProps) {
  const [scheduleData, setScheduleData] = useState<ScheduleItem[]>([]);
  const [priceData, setPriceData] = useState<PriceData[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [totalCharging, setTotalCharging] = useState<number>(0);

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
        
        // Zpracování dat a seřazení podle hodiny
        const processedData = data.schedule
          .map((item: ScheduleItem) => ({
            hour: item.hour,
            planned_charging_kwh: parseFloat(typeof item.planned_charging_kwh === 'string' ? 
              item.planned_charging_kwh : 
              item.planned_charging_kwh.toString()
            ),
          }))
          .sort((a: ScheduleItem, b: ScheduleItem) => a.hour - b.hour);
        
        setScheduleData(processedData);
        
        // Výpočet celkového plánovaného nabíjení
        const total = processedData.reduce(
          (sum: number, item: ScheduleItem) => sum + (item.planned_charging_kwh as number), 
          0
        );
        setTotalCharging(total);
        
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

  // Funkce pro získání informací o ceně pro hodinu
  const getPriceInfo = (hour: number) => {
    const price = priceData.find(p => p.hour === hour);
    if (!price) return null;
    
    return {
      priceValue: (price.price_czk / 1000).toFixed(2)
    };
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

  return (
    <div className="space-y-4 bg-white p-6 rounded-xl shadow-lg border border-gray-200">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold text-gray-800 mb-1 flex items-center">
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

      {scheduleData.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-6 text-center border border-gray-200">
          <p className="text-gray-600">{message || "Pro tento den není naplánováno žádné nabíjení ze sítě."}</p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm text-gray-500">Celkové plánované nabíjení:</span>
            <span className="text-xl font-bold text-blue-600">{totalCharging.toFixed(2)} kWh</span>
          </div>
          
          <div className="space-y-3">
            {scheduleData.map((item) => {
              const priceInfo = getPriceInfo(item.hour);
              
              return (
                <div 
                  key={item.hour} 
                  className="border rounded-lg bg-gray-50 p-4 flex flex-col md:flex-row md:items-center md:justify-between"
                >
                  <div className="flex items-center mb-2 md:mb-0">
                    <div className="flex items-center justify-center w-12 h-12 rounded-full bg-blue-100 text-blue-700 mr-4">
                      <span className="font-bold">{item.hour}:00</span>
                    </div>
                    <div>
                      <div className="flex items-center">
                        <span className="font-medium">Plánované nabíjení:</span>
                        <span className="ml-2 font-bold text-blue-600">
                          {(item.planned_charging_kwh as number).toFixed(2)} kWh
                        </span>
                      </div>
                      {priceInfo && (
                        <div className="text-sm text-gray-600 mt-0.5">
                          Cena: {priceInfo.priceValue} Kč/kWh
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
      
      <div className="mt-4 text-sm text-gray-500 bg-gray-50 p-4 rounded-lg">
        <p>Zobrazeno plánované nabíjení baterie ze sítě na základě optimalizace podle spotových cen elektřiny. Nabíjení ze solárních panelů není zahrnuto.</p>
      </div>
    </div>
  );
}