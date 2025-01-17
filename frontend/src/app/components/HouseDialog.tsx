"use client";

import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Plus } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface HouseDialogProps {
  onSuccess: () => void;
}

export default function HouseDialog({ onSuccess }: HouseDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    solar_power: '',
    battery_capacity: ''
  });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/houses/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name,
          solar_power: parseFloat(formData.solar_power),
          battery_capacity: parseFloat(formData.battery_capacity)
        }),
      });

      if (!response.ok) throw new Error('Nepodařilo se vytvořit dům');

      onSuccess();
      setIsOpen(false);
      setFormData({ name: '', solar_power: '', battery_capacity: '' });
    } catch (err) {
      setError('Nepodařilo se vytvořit dům');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Přidat dům
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Přidat nový dům</DialogTitle>
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
              {isLoading ? "Vytvářím..." : "Vytvořit"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}