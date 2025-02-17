import React from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { Appliance } from "@/types/appliance";
import ApplianceDialog from "./ApplianceDialog";

interface ApplianceListProps {
  appliances: Appliance[];
  houseId: number;
  onSuccess: () => void;
  onDelete: (id: number) => void;
}

const APPLIANCE_TYPES = [
  {
    type: "CONSTANT",
    title: "Konstantní spotřeba",
    description: "Spotřebiče s neměnnou spotřebou energie, které běží nepřetržitě.",
    examples: ["Router", "Server", "Bezpečnostní systém"],
    details: [
      "Běží 24/7 bez přerušení",
      "Stabilní odběr energie",
      "Nevyžaduje nastavení časových oken",
      "Vhodné pro zařízení, která musí být stále v provozu"
    ]
  },
  {
    type: "CYCLIC",
    title: "Cyklická spotřeba",
    description: "Spotřebiče střídající fáze aktivního běhu a pohotovostního režimu v pravidelných cyklech.",
    examples: ["Lednice", "Mraznička", "Klimatizace"],
    details: [
      "Střídá aktivní a pohotovostní režim",
      "Nastavitelná délka cyklů",
      "Definovaná spotřeba v pohotovostním režimu",
      "Vhodné pro termostaticky řízená zařízení"
    ]
  },
  {
    type: "SCHEDULED",
    title: "Plánovaná spotřeba",
    description: "Spotřebiče spouštěné v definovaných časových oknech s možností nastavení pravděpodobnosti spuštění.",
    examples: ["Pračka", "Myčka", "Bojler"],
    details: [
      "Běží v nastavených časových oknech",
      "Nastavitelná pravděpodobnost spuštění",
      "Různá nastavení pro pracovní dny a víkendy",
      "Vhodné pro zařízení s pravidelným používáním"
    ]
  },
  {
    type: "ON_DEMAND",
    title: "Spotřeba na vyžádání",
    description: "Spotřebiče s nepravidelným používáním v definovaných časových oknech s možností více spuštění.",
    examples: ["Varná konvice", "Mikrovlnka", "Trouba"],
    details: [
      "Více spuštění v časových oknech",
      "Nastavitelný počet použití",
      "Vhodné pro spotřebiče používané několikrát denně",
      "Flexibilní délka běhu"
    ]
  }
];

const ApplianceList = ({ appliances, houseId, onSuccess, onDelete }: ApplianceListProps) => {
  const [isOpen, setIsOpen] = React.useState(true);

  if (appliances.length === 0) {
    return (
      <Card className="bg-white shadow-sm border border-gray-100">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-xl font-semibold text-gray-900">
              Spotřebiče
            </CardTitle>
            <ApplianceDialog
              houseId={houseId}
              onSuccess={onSuccess}
            />
          </div>
        </CardHeader>
        <CardContent>
          <div className="p-6 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Průvodce typy spotřebičů</h3>
            <p className="text-sm text-gray-600 mb-4">
              Vyberte typ spotřebiče podle jeho charakteristiky. Kliknutím zobrazíte více informací.
            </p>
            <Accordion type="single" collapsible className="w-full space-y-4">
              {APPLIANCE_TYPES.map((appType) => (
                <AccordionItem 
                  key={appType.type}
                  value={appType.type}
                  className="border rounded-lg bg-white px-4"
                >
                  <AccordionTrigger className="hover:no-underline py-4">
                    <div className="flex items-center justify-between w-full">
                      <div className="flex items-center gap-3">
                        <span className="font-medium">{appType.title}</span>
                        <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                          {appType.type}
                        </span>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="pb-4">
                    <div className="space-y-4">
                      <p className="text-sm text-gray-600">{appType.description}</p>
                      
                      <div className="space-y-2">
                        <h4 className="text-sm font-medium text-gray-900">Charakteristiky:</h4>
                        <ul className="list-disc pl-5 text-sm text-gray-600 space-y-1">
                          {appType.details.map((detail, index) => (
                            <li key={index}>{detail}</li>
                          ))}
                        </ul>
                      </div>

                      <div className="space-y-2">
                        <h4 className="text-sm font-medium text-gray-900">Příklady:</h4>
                        <div className="flex gap-2 flex-wrap">
                          {appType.examples.map((example, index) => (
                            <span 
                              key={index}
                              className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded-full"
                            >
                              {example}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white shadow-sm border border-gray-100">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-xl font-semibold text-gray-900">
              Spotřebiče ({appliances.length})
            </CardTitle>
            <div className="flex gap-2">
              <ApplianceDialog
                houseId={houseId}
                onSuccess={onSuccess}
              />
              <CollapsibleTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon"
                >
                  {isOpen ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
            </div>
          </div>
        </CardHeader>
        
        <CollapsibleContent>
          <CardContent>
            <div className="space-y-4">
              {appliances.map((appliance) => (
                <div
                  key={appliance.id}
                  className="p-4 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="font-medium text-gray-900">
                        {appliance.name}
                      </h3>
                      <p className="text-sm text-gray-600">
                        Spotřeba: {appliance.power_consumption} W
                      </p>
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 mt-2">
                        {appliance.appliance_type}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <ApplianceDialog
                        houseId={houseId}
                        appliance={appliance}
                        onSuccess={onSuccess}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-red-500 hover:text-red-700 hover:bg-red-50"
                        onClick={() => onDelete(appliance.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

export default ApplianceList;