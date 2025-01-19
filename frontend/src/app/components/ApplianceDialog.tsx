"use client";

import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Pencil } from "lucide-react";
import TimeWindowInput from "./TimeWindowInput";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Appliance {
  id?: number;
  name: string;
  power_consumption: number;
  appliance_type: "CONSTANT" | "CYCLIC" | "SCHEDULED" | "ON_DEMAND";
  run_duration?: number;
  pause_duration?: number;
  usage_duration?: number;
  uses_per_window?: number;
  weekday_probability: number;
  weekend_probability: number;
  weekday_hours: number[][];
  weekend_hours: number[][];
}

interface ApplianceDialogProps {
  houseId: number;
  appliance?: Appliance;
  onSuccess: () => void;
}

export default function ApplianceDialog({
  houseId,
  appliance,
  onSuccess,
}: ApplianceDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    power_consumption: "",
    appliance_type: "",
    run_duration: "",
    pause_duration: "",
    usage_duration: "",
    uses_per_window: "",
    weekday_probability: "1",
    weekend_probability: "1",
    weekday_hours: [[0, 24]],
    weekend_hours: [[0, 24]],
  });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (appliance) {
      setFormData({
        name: appliance.name,
        power_consumption: appliance.power_consumption.toString(),
        appliance_type: appliance.appliance_type,
        run_duration: appliance.run_duration?.toString() || "",
        pause_duration: appliance.pause_duration?.toString() || "",
        usage_duration: appliance.usage_duration?.toString() || "",
        uses_per_window: appliance.uses_per_window?.toString() || "",
        weekday_probability: appliance.weekday_probability.toString(),
        weekend_probability: appliance.weekend_probability.toString(),
        weekday_hours: appliance.weekday_hours,
        weekend_hours: appliance.weekend_hours,
      });
    }
  }, [appliance]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      let url = `${API_URL}/api/houses/${houseId}/appliances/`;
      let method = "POST";

      if (appliance?.id) {
        url += `?id=${appliance.id}`;
        method = "PATCH";
      }

      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: formData.name,
          power_consumption: parseInt(formData.power_consumption),
          appliance_type: formData.appliance_type,
          ...(formData.appliance_type === "CYCLIC" && {
            run_duration: parseInt(formData.run_duration),
            pause_duration: parseInt(formData.pause_duration),
          }),
          ...(formData.appliance_type === "SCHEDULED" && {
            usage_duration: parseInt(formData.usage_duration),
            weekday_probability: parseFloat(formData.weekday_probability),
            weekend_probability: parseFloat(formData.weekend_probability),
            weekday_hours: formData.weekday_hours,
            weekend_hours: formData.weekend_hours,
          }),
          ...(formData.appliance_type === "ON_DEMAND" && {
            usage_duration: parseInt(formData.usage_duration),
            uses_per_window: parseInt(formData.uses_per_window),
            weekday_probability: parseFloat(formData.weekday_probability),
            weekend_probability: parseFloat(formData.weekend_probability),
            weekday_hours: formData.weekday_hours,
            weekend_hours: formData.weekend_hours,
          }),
        }),
      });

      if (!response.ok) throw new Error("Nepodařilo se uložit spotřebič");

      onSuccess();
      setIsOpen(false);
      if (!appliance) {
        setFormData({
          name: "",
          power_consumption: "",
          appliance_type: "",
          run_duration: "",
          pause_duration: "",
          usage_duration: "",
          uses_per_window: "",
          weekday_probability: "1",
          weekend_probability: "1",
          weekday_hours: [[0, 24]],
          weekend_hours: [[0, 24]],
        });
      }
    } catch (err) {
      setError("Nepodařilo se uložit spotřebič");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        {appliance ? (
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
            Přidat spotřebič
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {appliance ? "Upravit spotřebič" : "Přidat nový spotřebič"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Základní údaje pro všechny typy */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Název spotřebiče
              </label>
              <Input
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Např. Lednice"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Spotřeba (W)
              </label>
              <Input
                type="number"
                min="0"
                value={formData.power_consumption}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    power_consumption: e.target.value,
                  })
                }
                placeholder="Např. 100"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Typ spotřebiče
              </label>
              <Select
                value={formData.appliance_type}
                onValueChange={(
                  value: "CONSTANT" | "CYCLIC" | "SCHEDULED" | "ON_DEMAND"
                ) => setFormData({ ...formData, appliance_type: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Vyberte typ spotřebiče" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CONSTANT">
                    Konstantní spotřeba (router)
                  </SelectItem>
                  <SelectItem value="CYCLIC">
                    Cyklická spotřeba (lednice)
                  </SelectItem>
                  <SelectItem value="SCHEDULED">
                    Plánovaná spotřeba (pračka)
                  </SelectItem>
                  <SelectItem value="ON_DEMAND">
                    Spotřeba na vyžádání (konvice)
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Pole pro CYCLIC typ */}
          {formData.appliance_type === "CYCLIC" && (
            <div className="space-y-4 border-t pt-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Doba běhu cyklu (minuty)
                </label>
                <Input
                  type="number"
                  min="1"
                  value={formData.run_duration}
                  onChange={(e) =>
                    setFormData({ ...formData, run_duration: e.target.value })
                  }
                  placeholder="Např. 30"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  Doba pauzy cyklu (minuty)
                </label>
                <Input
                  type="number"
                  min="1"
                  value={formData.pause_duration}
                  onChange={(e) =>
                    setFormData({ ...formData, pause_duration: e.target.value })
                  }
                  placeholder="Např. 60"
                  required
                />
              </div>
            </div>
          )}

          {/* Pole pro SCHEDULED a ON_DEMAND typy */}
          {(formData.appliance_type === "SCHEDULED" ||
            formData.appliance_type === "ON_DEMAND") && (
            <div className="space-y-4 border-t pt-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Délka použití (minuty)
                </label>
                <Input
                  type="number"
                  min="1"
                  value={formData.usage_duration}
                  onChange={(e) =>
                    setFormData({ ...formData, usage_duration: e.target.value })
                  }
                  placeholder="Např. 120"
                  required
                />
              </div>

              {formData.appliance_type === "ON_DEMAND" && (
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Počet použití v časovém okně
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.uses_per_window}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        uses_per_window: e.target.value,
                      })
                    }
                    placeholder="Např. 2"
                    required
                  />
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Pravděpodobnost použití - pracovní dny (%)
                  </label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={parseFloat(formData.weekday_probability) * 100}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        weekday_probability: (
                          parseInt(e.target.value) / 100
                        ).toString(),
                      })
                    }
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Pravděpodobnost použití - víkendy (%)
                  </label>
                  <Input
                    type="number"
                    min="0"
                    max="100"
                    value={parseFloat(formData.weekend_probability) * 100}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        weekend_probability: (
                          parseInt(e.target.value) / 100
                        ).toString(),
                      })
                    }
                    required
                  />
                </div>
              </div>

              <div className="space-y-4">
                <TimeWindowInput
                  windows={formData.weekday_hours}
                  onChange={(windows) =>
                    setFormData({ ...formData, weekday_hours: windows })
                  }
                  label="Časová okna - pracovní dny"
                />

                <TimeWindowInput
                  windows={formData.weekend_hours}
                  onChange={(windows) =>
                    setFormData({ ...formData, weekend_hours: windows })
                  }
                  label="Časová okna - víkendy"
                />
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsOpen(false)}
            >
              Zrušit
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? "Ukládám..." : appliance ? "Uložit" : "Přidat"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
