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
import { Appliance, TimeWindow } from "@/types/appliance";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FormData {
  name: string;
  power_consumption: string;
  standby_power: string;
  appliance_type: Appliance["appliance_type"] | "";
  run_duration_min: string;
  run_duration_max: string;
  pause_duration_min: string;
  pause_duration_max: string;
  usage_duration_min: string;
  usage_duration_max: string;
  weekday_hours: TimeWindow[];
  weekend_hours: TimeWindow[];
  priority_level: number;
  interruptible: boolean;
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
  const [formData, setFormData] = useState<FormData>({
    name: "",
    power_consumption: "",
    standby_power: "",
    appliance_type: "",
    run_duration_min: "",
    run_duration_max: "",
    pause_duration_min: "",
    pause_duration_max: "",
    usage_duration_min: "",
    usage_duration_max: "",
    weekday_hours: [],
    weekend_hours: [],
    priority_level: 1,
    interruptible: true
  });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (appliance) {
      setFormData({
        name: appliance.name,
        power_consumption: appliance.power_consumption.toString(),
        standby_power: appliance.standby_power?.toString() || "",
        appliance_type: appliance.appliance_type,
        run_duration_min:
          appliance.run_duration_min != null
            ? appliance.run_duration_min.toString()
            : "",
        run_duration_max:
          appliance.run_duration_max != null
            ? appliance.run_duration_max.toString()
            : "",
        pause_duration_min:
          appliance.pause_duration_min != null
            ? appliance.pause_duration_min.toString()
            : "",
        pause_duration_max:
          appliance.pause_duration_max != null
            ? appliance.pause_duration_max.toString()
            : "",
        usage_duration_min: appliance.usage_duration_min?.toString() || "",
        usage_duration_max: appliance.usage_duration_max?.toString() || "",
        weekday_hours: appliance.weekday_hours || [],
        weekend_hours: appliance.weekend_hours || [],
        priority_level: appliance.priority_level || 1,
        interruptible: appliance.interruptible !== false // Pokud undefined nebo true, vrátí true
      });
    }
  }, [appliance]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      // Validace standby_power pro CYCLIC typ
      if (formData.appliance_type === "CYCLIC" && !formData.standby_power) {
        setError(
          "Pro cyklické spotřebiče je povinné vyplnit spotřebu v pohotovostním režimu"
        );
        setIsLoading(false);
        return;
      }

      if (formData.appliance_type === "CYCLIC") {
        const runMin = parseInt(formData.run_duration_min);
        const runMax = parseInt(formData.run_duration_max);
        const pauseMin = parseInt(formData.pause_duration_min);
        const pauseMax = parseInt(formData.pause_duration_max);

        if (runMin > runMax) {
          setError("Maximální doba běhu musí být delší než minimální");
          setIsLoading(false);
          return;
        }

        if (pauseMin > pauseMax) {
          setError("Maximální doba pauzy musí být delší než minimální");
          setIsLoading(false);
          return;
        }
      }

      if (
        formData.appliance_type === "SCHEDULED" ||
        formData.appliance_type === "ON_DEMAND"
      ) {
        const usageMin = parseInt(formData.usage_duration_min);
        const usageMax = parseInt(formData.usage_duration_max);

        if (usageMin > usageMax) {
          setError("Maximální doba běhu musí být delší než minimální");
          setIsLoading(false);
          return;
        }
      }

      // Zajištění, že všechna časová okna mají flag is_active
      const processedWeekdayHours = formData.weekday_hours.map(window => ({
        ...window,
        is_active: window.is_active !== false // Defaultně true, pokud není explicitně false
      }));
      
      const processedWeekendHours = formData.weekend_hours.map(window => ({
        ...window,
        is_active: window.is_active !== false // Defaultně true, pokud není explicitně false
      }));

      let url = `${API_URL}/api/houses/${houseId}/appliances/`;
      let method = "POST";

      if (appliance?.id) {
        url += `?id=${appliance.id}`;
        method = "PATCH";
      }

      const response = await fetch(url, {
        method,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: formData.name,
          power_consumption: parseInt(formData.power_consumption),
          appliance_type: formData.appliance_type,
          priority_level: formData.priority_level,
          interruptible: formData.interruptible,
          ...(formData.appliance_type === "CYCLIC" && {
            standby_power: parseInt(formData.standby_power), // Povinné pro CYCLIC
            run_duration_min: parseInt(formData.run_duration_min),
            run_duration_max: parseInt(formData.run_duration_max),
            pause_duration_min: parseInt(formData.pause_duration_min),
            pause_duration_max: parseInt(formData.pause_duration_max),
          }),
          ...(formData.appliance_type === "SCHEDULED" && {
            standby_power: formData.standby_power
              ? parseInt(formData.standby_power)
              : 0,
            usage_duration_min: parseInt(formData.usage_duration_min),
            usage_duration_max: parseInt(formData.usage_duration_max),
            weekday_hours: processedWeekdayHours,
            weekend_hours: processedWeekendHours,
          }),
          ...(formData.appliance_type === "ON_DEMAND" && {
            usage_duration_min: parseInt(formData.usage_duration_min),
            usage_duration_max: parseInt(formData.usage_duration_max),
            weekday_hours: processedWeekdayHours,
            weekend_hours: processedWeekendHours,
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
          standby_power: "",
          appliance_type: "",
          run_duration_min: "",
          run_duration_max: "",
          pause_duration_min: "",
          pause_duration_max: "",
          usage_duration_min: "",
          usage_duration_max: "",
          weekday_hours: [],
          weekend_hours: [],
          priority_level: 1,
          interruptible: true
        });
      }
    } catch (err) {
      setError("Nepodařilo se uložit spotřebič");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const renderStandbyPowerInput = () => {
    // Zobrazit jen pro CYCLIC a SCHEDULED
    if (
      !formData.appliance_type ||
      formData.appliance_type === "CONSTANT" ||
      formData.appliance_type === "ON_DEMAND"
    )
      return null;

    const isRequired = formData.appliance_type === "CYCLIC";

    return (
      <div>
        <label className="block text-sm font-medium mb-1">
          {isRequired
            ? "Spotřeba v pohotovostním režimu (W) *"
            : "Spotřeba v pohotovostním režimu (W)"}
        </label>
        <Input
          type="number"
          min="0"
          value={formData.standby_power}
          onChange={(e) =>
            setFormData({
              ...formData,
              standby_power: e.target.value,
            })
          }
          placeholder={
            isRequired ? "Povinné pole" : "Volitelné pole (výchozí 0)"
          }
          required={isRequired}
        />
      </div>
    );
  };

  // Nová sekce pro prioritu a přerušitelnost
  const renderOptimizationSection = () => {
    return (
      <div className="space-y-4 border-t pt-4 mt-4">
        <h3 className="text-lg font-medium">Nastavení optimalizace spotřeby</h3>
        
        <div>
          <label className="block text-sm font-medium mb-1">
            Priorita spotřebiče
          </label>
          <Select
            value={formData.priority_level.toString()}
            onValueChange={(value) => setFormData({...formData, priority_level: parseInt(value)})}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Vyberte prioritu" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Kritický - nikdy nevypínat</SelectItem>
              <SelectItem value="2">Vysoká priorita - vypnout v krajní nouzi</SelectItem>
              <SelectItem value="3">Střední priorita - možné vypnout při vysokých cenách</SelectItem>
              <SelectItem value="4">Nízká priorita - vypnout jako první</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-gray-500 mt-1">
            Určuje, jak důležitý je spotřebič a v jakém pořadí bude vypínán při optimalizaci.
          </p>
        </div>
        
        <div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="interruptible"
              checked={formData.interruptible}
              onChange={(e) =>
                setFormData({...formData, interruptible: e.target.checked})
              }
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="interruptible" className="ml-2 block text-sm text-gray-700">
              Lze přerušit za běhu
            </label>
          </div>
          <p className="text-xs text-gray-500 mt-1 ml-6">
            Pokud je zaškrtnuto, spotřebič může být vypnut i když právě běží.
            Vhodné např. pro osvětlení nebo televizi, ale ne pro pračku nebo troubu.
          </p>
        </div>
      </div>
    );
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

            {renderStandbyPowerInput()}
          </div>

          {/* Pole pro CYCLIC typ */}
          {formData.appliance_type === "CYCLIC" && (
            <div className="space-y-4 border-t pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Minimální doba běhu (minuty)
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.run_duration_min}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        run_duration_min: e.target.value,
                      })
                    }
                    placeholder="Např. 10"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Maximální doba běhu (minuty)
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.run_duration_max}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        run_duration_max: e.target.value,
                      })
                    }
                    placeholder="Např. 15"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Minimální doba pauzy (minuty)
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.pause_duration_min}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        pause_duration_min: e.target.value,
                      })
                    }
                    placeholder="Např. 30"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Maximální doba pauzy (minuty)
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.pause_duration_max}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        pause_duration_max: e.target.value,
                      })
                    }
                    placeholder="Např. 45"
                    required
                  />
                </div>
              </div>
            </div>
          )}

          {/* Pole pro SCHEDULED a ON_DEMAND typy */}
          {(formData.appliance_type === "SCHEDULED" ||
            formData.appliance_type === "ON_DEMAND") && (
            <div className="space-y-4 border-t pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Minimální doba běhu (minuty)
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.usage_duration_min}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        usage_duration_min: e.target.value,
                      })
                    }
                    placeholder="Např. 30"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Maximální doba běhu (minuty)
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.usage_duration_max}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        usage_duration_max: e.target.value,
                      })
                    }
                    placeholder="Např. 120"
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
                  maxWindows={24}
                  showUses={formData.appliance_type === "ON_DEMAND"}
                />

                <TimeWindowInput
                  windows={formData.weekend_hours}
                  onChange={(windows) =>
                    setFormData({ ...formData, weekend_hours: windows })
                  }
                  label="Časová okna - víkendy"
                  maxWindows={24}
                  showUses={formData.appliance_type === "ON_DEMAND"}
                />
              </div>
            </div>
          )}

          {/* Sekce pro nastavení optimalizace */}
          {renderOptimizationSection()}

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