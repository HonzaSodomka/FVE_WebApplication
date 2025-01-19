import React from 'react';
import { Button } from '@/components/ui/button';
import { Trash2 } from 'lucide-react';

interface TimeWindowInputProps {
    windows: number[][];
    onChange: (windows: number[][]) => void;
    label: string;
    maxWindows?: number;
  }
  
  const TimeWindowInput: React.FC<TimeWindowInputProps> = ({ 
    windows, 
    onChange, 
    label,
    maxWindows = 3 
  }) => {
    const addWindow = () => {
      if (windows.length < maxWindows) {
        onChange([...windows, [0, 24]]);
      }
    };
  
    const removeWindow = (index: number) => {
      onChange(windows.filter((_, i) => i !== index));
    };
  
    const updateWindow = (index: number, field: 'start' | 'end', value: number) => {
      const newWindows = [...windows];
      newWindows[index][field === 'start' ? 0 : 1] = value;
      onChange(newWindows);
    };
  
    return (
      <div className="space-y-2">
        <label className="text-sm text-gray-600 mb-2 block">{label}</label>
        {windows.map((window, index) => (
          <div key={index} className="flex items-center gap-2 mb-2">
            <div className="flex-1 grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-500">Od</label>
                <select
                  className="w-full border rounded p-2"
                  value={window[0]}
                  onChange={(e) => updateWindow(index, 'start', parseInt(e.target.value))}
                >
                  {Array.from({ length: 25 }, (_, i) => (
                    <option key={i} value={i}>{i}:00</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500">Do</label>
                <select
                  className="w-full border rounded p-2"
                  value={window[1]}
                  onChange={(e) => updateWindow(index, 'end', parseInt(e.target.value))}
                >
                  {Array.from({ length: 25 }, (_, i) => (
                    <option key={i} value={i}>{i}:00</option>
                  ))}
                </select>
              </div>
            </div>
            {windows.length > 1 && (
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
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addWindow}
          >
            Přidat časové okno
          </Button>
        )}
      </div>
    );
  };
  
  export default TimeWindowInput;