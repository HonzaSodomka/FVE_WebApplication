"use client";

import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Pencil } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface House {
  id: number;
  name: string;
  solar_power: number;
  battery_capacity: number;
  current_battery_level: number;
  min_battery_level: number;
  max_charging_power: number;
  max_discharging_power: number;
  charging_efficiency: number;
  discharging_efficiency: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  is_active: boolean;
}

interface HouseDialogProps {
  house?: House;
  onSuccess: () => void;
}

export default function HouseDialog({ house, onSuccess }: HouseDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  
  const [formData, setFormData] = useState({
    name: '',
    solar_power: '',
    battery_capacity: '',
    current_battery_level: '0',
    min_battery_level: '10',
    max_charging_power: '',
    max_discharging_power: '',
    charging_efficiency: '90',
    discharging_efficiency: '90',
    risk_level: 'MEDIUM' as 'LOW' | 'MEDIUM' | 'HIGH'
  });
  
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (house) {
      setFormData({
        name: house.name,
        solar_power: house.solar_power.toString(),
        battery_capacity: house.battery_capacity.toString(),
        current_battery_level: house.current_battery_level.toString(),
        min_battery_level: house.min_battery_level.toString(),
        max_charging_power: house.max_charging_power.toString(),
        max_discharging_power: house.max_discharging_power.toString(),
        charging_efficiency: house.charging_efficiency.toString(),
        discharging_efficiency: house.discharging_efficiency.toString(),
        risk_level: house.risk_level
      });
    }
  }, [house]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      let url = `${API_URL}/api/houses/`;
      let method = 'POST';

      if (house?.id) {
        url += `?id=${house.id}`;
        method = 'PATCH';
      }

      const response = await fetch(url, {
        method,
        credentials: "include",
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name,
          solar_power: parseFloat(formData.solar_power),
          battery_capacity: parseFloat(formData.battery_capacity),
          current_battery_level: parseFloat(formData.current_battery_level),
          min_battery_level: parseFloat(formData.min_battery_level),
          max_charging_power: parseFloat(formData.max_charging_power),
          max_discharging_power: parseFloat(formData.max_discharging_power),
          charging_efficiency: parseFloat(formData.charging_efficiency),
          discharging_efficiency: parseFloat(formData.discharging_efficiency),
          risk_level: formData.risk_level
        }),
      });

      if (!response.ok) throw new Error('Nepodařilo se uložit dům');

      onSuccess();
      setIsOpen(false);
      
      if (!house) {
        setFormData({
          name: '',
          solar_power: '',
          battery_capacity: '',
          current_battery_level: '0',
          min_battery_level: '10',
          max_charging_power: '',
          max_discharging_power: '',
          charging_efficiency: '90',
          discharging_efficiency: '90',
          risk_level: 'MEDIUM'
        });
      }
    } catch (err) {
      setError('Nepodařilo se uložit dům');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        {house ? (
          <Button
            variant="ghost"
            size="icon"
            className="text-blue-500 hover:text-blue-700 hover:bg-blue-50"
          >
            <Pencil className="h-4 w-4" />
          </Button>
        ) : (
          <Button className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Přidat dům
          </Button>
        )}
      </DialogTrigger>
      
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader className="sticky top-0 bg-white pb-4 border-b">
          <DialogTitle>
            {house ? 'Upravit dům' : 'Přidat nový dům'}
          </DialogTitle>
        </DialogHeader>
        
        <div className="py-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Název domu
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  placeholder="Např. Můj dům"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Výkon solárních panelů (kWp)
                </label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  value={formData.solar_power}
                  onChange={(e) => setFormData({...formData, solar_power: e.target.value})}
                  placeholder="Např. 10.0"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Kapacita baterie (kWh)
                </label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  value={formData.battery_capacity}
                  onChange={(e) => setFormData({...formData, battery_capacity: e.target.value})}
                  placeholder="Např. 10.0"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Maximální nabíjecí výkon (kW)
                </label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  value={formData.max_charging_power}
                  onChange={(e) => setFormData({...formData, max_charging_power: e.target.value})}
                  placeholder="Např. 3.0"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Maximální vybíjecí výkon (kW)
                </label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  value={formData.max_discharging_power}
                  onChange={(e) => setFormData({...formData, max_discharging_power: e.target.value})}
                  placeholder="Např. 3.0"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Minimální úroveň baterie (%)
                </label>
                <Input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={formData.min_battery_level}
                  onChange={(e) => setFormData({...formData, min_battery_level: e.target.value})}
                  placeholder="Např. 10"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Účinnost nabíjení (%)
                </label>
                <Input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={formData.charging_efficiency}
                  onChange={(e) => setFormData({...formData, charging_efficiency: e.target.value})}
                  placeholder="Např. 90"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Účinnost vybíjení (%)
                </label>
                <Input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={formData.discharging_efficiency}
                  onChange={(e) => setFormData({...formData, discharging_efficiency: e.target.value})}
                  placeholder="Např. 90"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Úroveň rizika
                </label>
                <Select 
                  value={formData.risk_level}
                  onValueChange={(value: 'LOW' | 'MEDIUM' | 'HIGH') => 
                    setFormData({...formData, risk_level: value})
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Vyberte úroveň rizika" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="LOW">Nízké - Nabíjí i za vyšší ceny</SelectItem>
                    <SelectItem value="MEDIUM">Střední - Vyvážený přístup</SelectItem>
                    <SelectItem value="HIGH">Vysoké - Agresivní optimalizace ceny</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="sticky bottom-0 bg-white pt-4 border-t flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsOpen(false)}
              >
                Zrušit
              </Button>
              <Button
                type="submit"
                disabled={isLoading}
              >
                {isLoading ? "Ukládám..." : house ? "Uložit" : "Přidat"}
              </Button>
            </div>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
}