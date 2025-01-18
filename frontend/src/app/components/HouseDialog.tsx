"use client";

import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Plus, Pencil } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface House {
  id: number;
  name: string;
  solar_power: number;
  battery_capacity: number;
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
    battery_capacity: ''
  });
  
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Effect pro předvyplnění formuláře při editaci existujícího domu
  useEffect(() => {
    if (house) {
      setFormData({
        name: house.name,
        solar_power: house.solar_power.toString(),
        battery_capacity: house.battery_capacity.toString()
      });
    }
  }, [house]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      // Nastavení URL a metody podle toho, zda jde o vytvoření nebo úpravu
      let url = `${API_URL}/api/houses/`;
      let method = 'POST';

      if (house?.id) {
        url += `?id=${house.id}`;
        method = 'PATCH';
      }

      // Volání API pro uložení dat
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name,
          solar_power: parseFloat(formData.solar_power),
          battery_capacity: parseFloat(formData.battery_capacity)
        }),
      });

      if (!response.ok) throw new Error('Nepodařilo se uložit dům');

      onSuccess();
      setIsOpen(false);
      // Reset formuláře pouze při vytváření nového domu
      if (!house) {
        setFormData({
          name: '',
          solar_power: '',
          battery_capacity: ''
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
        {/* Podmíněné renderování tlačítka podle režimu (úprava/vytvoření) */}
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
      
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {house ? 'Upravit dům' : 'Přidat nový dům'}
          </DialogTitle>
        </DialogHeader>
        
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
          </div>

          <div className="flex justify-end gap-2">
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
      </DialogContent>
    </Dialog>
  );
}