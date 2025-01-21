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
 appliance_type: Appliance["appliance_type"] | "";
 run_duration_min: string;
 run_duration_max: string;
 pause_duration_min: string;
 pause_duration_max: string;
 usage_duration_min: string;
 usage_duration_max: string;
 weekday_hours: TimeWindow[];
 weekend_hours: TimeWindow[];
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
   appliance_type: "",
   run_duration_min: "",
   run_duration_max: "",
   pause_duration_min: "",
   pause_duration_max: "",
   usage_duration_min: "",
   usage_duration_max: "",
   weekday_hours: [],
   weekend_hours: [],
 });
 const [error, setError] = useState<string | null>(null);
 const [isLoading, setIsLoading] = useState(false);

 useEffect(() => {
   if (appliance) {
     setFormData({
       name: appliance.name,
       power_consumption: appliance.power_consumption.toString(),
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
         ...(formData.appliance_type === "CYCLIC" && {
           run_duration_min: parseInt(formData.run_duration_min),
           run_duration_max: parseInt(formData.run_duration_max),
           pause_duration_min: parseInt(formData.pause_duration_min),
           pause_duration_max: parseInt(formData.pause_duration_max),
         }),
         ...(formData.appliance_type === "SCHEDULED" && {
           usage_duration_min: parseInt(formData.usage_duration_min),
           usage_duration_max: parseInt(formData.usage_duration_max),
           weekday_hours: formData.weekday_hours,
           weekend_hours: formData.weekend_hours,
         }),
         ...(formData.appliance_type === "ON_DEMAND" && {
           usage_duration_min: parseInt(formData.usage_duration_min),
           usage_duration_max: parseInt(formData.usage_duration_max),
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
         run_duration_min: "",
         run_duration_max: "",
         pause_duration_min: "",
         pause_duration_max: "",
         usage_duration_min: "",
         usage_duration_max: "",
         weekday_hours: [],
         weekend_hours: [],
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
                 maxWindows={3}
                 showUses={formData.appliance_type === "ON_DEMAND"}
               />

               <TimeWindowInput
                 windows={formData.weekend_hours}
                 onChange={(windows) =>
                   setFormData({ ...formData, weekend_hours: windows })
                 }
                 label="Časová okna - víkendy"
                 maxWindows={3}
                 showUses={formData.appliance_type === "ON_DEMAND"}
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
