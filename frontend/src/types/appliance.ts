export interface TimeWindow {
  start: number;  
  end: number;
  probability: number;
  uses?: number; 
  is_active?: boolean;  // Přidání pole is_active pro optimalizaci
}

export interface InactiveWindow {
  date: string;
  start_hour: number;
  end_hour: number;
}

export interface Appliance {
  id: number;
  name: string;
  power_consumption: number;
  standby_power?: number | null;
  appliance_type: "CONSTANT" | "CYCLIC" | "SCHEDULED" | "ON_DEMAND";
  run_duration_min?: number | null;
  run_duration_max?: number | null;
  pause_duration_min?: number | null;
  pause_duration_max?: number | null;
  usage_duration_min?: number | null;
  usage_duration_max?: number | null;
  weekday_hours: TimeWindow[] | null;
  weekend_hours: TimeWindow[] | null;
  remaining_minutes_list?: number[] | null;
  planned_starts?: string[] | null;
  is_active?: boolean | null;
  in_standby?: boolean | null;
  remaining_minutes?: number | null;
  next_start_time?: string | null;
  
  // Nová pole pro optimalizaci spotřeby
  priority_level: number;
  interruptible: boolean;
  inactive_windows?: InactiveWindow[] | null;
}