import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2 } from "lucide-react";
import { TimeWindow } from "@/types/appliance";

interface TimeWindowInputProps {
  windows: TimeWindow[];
  onChange: (windows: TimeWindow[]) => void;
  label: string;
  maxWindows?: number;
  showUses?: boolean;
}

const TimeWindowInput: React.FC<TimeWindowInputProps> = ({
  windows,
  onChange,
  label,
  maxWindows = 12,
  showUses = false
}) => {
  const addWindow = () => {
    if (windows.length < maxWindows) {
      onChange([
        ...windows,
        {
          start: 0,
          end: 24,
          probability: 1.0,
          ...(showUses && { uses: 1 }),
        },
      ]);
    }
  };

  const removeWindow = (index: number) => {
    onChange(windows.filter((_, i) => i !== index));
  };

  const updateWindow = (
    index: number,
    field: keyof TimeWindow,
    value: number
  ) => {
    const newWindows = [...windows];
    if (field === "probability") {
      // Převod z procent na desetinné číslo
      newWindows[index][field] = value / 100;
    } else {
      newWindows[index][field] = value;
    }
    onChange(newWindows);
  };

  return (
    <div className="space-y-2">
      <label className="text-sm text-gray-600 mb-2 block">{label}</label>
      {windows.map((window, index) => (
        <div key={index} className="flex items-center gap-2 mb-2">
          <div className={`flex-1 grid ${showUses ? 'grid-cols-4' : 'grid-cols-3'} gap-2`}>
            <div>
              <label className="text-xs text-gray-500">Od</label>
              <select
                className="w-full border rounded p-2"
                value={window.start}
                onChange={(e) =>
                  updateWindow(index, "start", parseInt(e.target.value))
                }
              >
                {Array.from({ length: 25 }, (_, i) => (
                  <option key={i} value={i}>
                    {i}:00
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500">Do</label>
              <select
                className="w-full border rounded p-2"
                value={window.end}
                onChange={(e) =>
                  updateWindow(index, "end", parseInt(e.target.value))
                }
              >
                {Array.from({ length: 25 }, (_, i) => (
                  <option key={i} value={i}>
                    {i}:00
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500">
                Pravděpodobnost (%)
              </label>
              <Input
                type="number"
                min="0"
                max="100"
                className="w-full"
                value={Math.round(window.probability * 100)}
                onChange={(e) =>
                  updateWindow(index, "probability", parseInt(e.target.value))
                }
              />
            </div>
            {showUses && (
              <div>
                <label className="text-xs text-gray-500">Počet použití</label>
                <Input
                  type="number"
                  min="1"
                  className="w-full"
                  value={window.uses || 1}
                  onChange={(e) =>
                    updateWindow(index, "uses", parseInt(e.target.value))
                  }
                />
              </div>
            )}
          </div>
          {windows.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="text-red-500 hover:text-red-700 hover:bg-red-50"
              onClick={() => removeWindow(index)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      ))}
      {windows.length < maxWindows && (
        <Button type="button" variant="outline" size="sm" onClick={addWindow}>
          Přidat časové okno
        </Button>
      )}
    </div>
  );
};

export default TimeWindowInput;