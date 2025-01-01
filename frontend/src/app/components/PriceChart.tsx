"use client";

import { useState, useEffect } from 'react';
import { DatePicker } from "@/components/ui/date-picker";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Alert, AlertDescription } from "@/components/ui/alert";

interface PriceData {
  hour: number;
  price_czk: number;
  level: string;
  level_num: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const getLevelColor = (level: string) => {
  switch (level) {
    case 'high': return '#ef4444';
    case 'medium': return '#f59e0b';
    case 'low': return '#22c55e';
    default: return '#gray';
  }
};

export default function PriceChart() {
  const [prices, setPrices] = useState<PriceData[]>([]);
  const [date, setDate] = useState<Date>(new Date());
  const [error, setError] = useState<string>('');

  useEffect(() => {
    const fetchPrices = async () => {
      try {
        // Formátování datumu na lokální čas
        const formattedDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
        const response = await fetch(`${API_URL}/api/prices/?date=${formattedDate}`);
        const data = await response.json();

        if (data.prices.length === 0) {
          setError(`Pro datum ${formattedDate} nejsou k dispozici žádná data.`);
          setPrices([]);
        } else {
          setError('');
          setPrices(data.prices.sort((a: PriceData, b: PriceData) => a.hour - b.hour));
        }
      } catch (err) {
        setError('Nepodařilo se načíst data');
        console.error(err);
      }
    };

    fetchPrices();
  }, [date]);

  const chartData = prices.map(price => ({
    ...price,
    time: `${String(price.hour).padStart(2, '0')}:00`,
    color: getLevelColor(price.level)
  }));

  return (
    <div className="w-full space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Ceny elektřiny</h2>
        <DatePicker 
          date={date}
          onSelect={setDate}
        />
      </div>

      {error ? (
        <Alert>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : (
        <div className="h-96 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip 
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-white p-2 border rounded shadow">
                        <p className="font-bold">{data.time}</p>
                        <p>Cena: {data.price_czk} Kč</p>
                        <p>Level: {data.level}</p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Line 
                type="monotone" 
                dataKey="price_czk" 
                stroke="#2563eb"
                strokeWidth={2}
                dot={({ payload }) => (
                  <circle 
                    r={4} 
                    fill={payload.color}
                    stroke={payload.color}
                    strokeWidth={2}
                  />
                )}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
