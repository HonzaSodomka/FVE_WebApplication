"use client";

import { useState } from "react";
import PriceChart from "./components/PriceChart";
import SolarDataChart from "./components/SolarDataChart";
import { DatePicker } from "@/components/ui/date-picker";

export default function Home() {
  const [date, setDate] = useState<Date>(() => new Date());

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8 bg-white p-6 rounded-lg shadow-lg">
          <h1 className="text-3xl font-bold text-gray-800 mb-4">
            Energetický Dashboard
          </h1>
          <div className="flex justify-between items-center">
            <p className="text-lg text-gray-600">
              Přehled cen elektřiny a solární produkce
            </p>
            <DatePicker date={date} onSelect={setDate} />
          </div>
        </header>

        <div className="space-y-8">
          <section className="bg-white rounded-lg shadow-lg p-6 transition-all duration-300 ease-in-out transform hover:-translate-y-1 hover:shadow-xl">
            <PriceChart date={date} />
          </section>
          <section className="bg-white rounded-lg shadow-lg p-6 transition-all duration-300 ease-in-out transform hover:-translate-y-1 hover:shadow-xl">
            <SolarDataChart date={date} />
          </section>
        </div>
      </div>
    </main>
  );
}
