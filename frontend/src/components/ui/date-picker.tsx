"use client"

// Import potřebných komponent a utilit
import * as React from "react";
import { format } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover } from "@/components/ui/popover";
import { PopoverContent } from "@/components/ui/popover";
import { PopoverTrigger } from "@/components/ui/popover";

// Interface pro props komponenty
interface DatePickerProps {
  date?: Date;           // Vybrané datum (nepovinné)
  onSelect?: (date: Date) => void;  // Callback při výběru data (nepovinné)
}

export function DatePicker({ date, onSelect }: DatePickerProps) {
  return (
    // Popover = vysouvací menu
    <Popover>
      {/* Tlačítko které otevře kalendář */}
      <PopoverTrigger asChild>
        <Button
          variant={"outline"}
          className={cn(
            "w-[240px] justify-start text-left font-normal",
            !date && "text-muted-foreground"  // Šedý text když není vybráno datum
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {date ? format(date, "PPP") : <span>Vyberte datum</span>}
        </Button>
      </PopoverTrigger>

      {/* Obsah kalendáře */}
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"  // Lze vybrat jen jedno datum
          selected={date}
          onSelect={(newDate) => {
            if (newDate && onSelect) {
              // Reset hodin na půlnoc podle lokálního času
              const selectedDate = new Date(
                newDate.getFullYear(),
                newDate.getMonth(),
                newDate.getDate()
              );
              onSelect(selectedDate);
            }
          }}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}