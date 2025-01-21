// src/types/appliance.ts
export interface TimeWindow {
  start: number;  
  end: number;
  probability: number;
  uses?: number; 
}

export interface Appliance {
  id?: number;
  name: string;
  power_consumption: number;
  appliance_type: "CONSTANT" | "CYCLIC" | "SCHEDULED" | "ON_DEMAND";
  run_duration_min?: number | null;
  run_duration_max?: number | null;
  pause_duration_min?: number | null;
  pause_duration_max?: number | null;
  usage_duration_min?: number | null;
  usage_duration_max?: number | null;
  weekday_hours: TimeWindow[];
  weekend_hours: TimeWindow[];
}