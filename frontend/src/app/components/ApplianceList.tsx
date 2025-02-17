import React from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { Appliance } from "@/types/appliance";
import ApplianceDialog from "./ApplianceDialog";

interface ApplianceListProps {
  appliances: Appliance[];
  houseId: number;
  onSuccess: () => void;
  onDelete: (id: number) => void;
}

const ApplianceList = ({ appliances, houseId, onSuccess, onDelete }: ApplianceListProps) => {
  const [isOpen, setIsOpen] = React.useState(true);

  if (appliances.length === 0) {
    return (
      <div className="text-center p-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200">
        <p className="text-gray-500 mb-4">
          Zatím nejsou přidány žádné spotřebiče
        </p>
        <ApplianceDialog
          houseId={houseId}
          onSuccess={onSuccess}
        />
      </div>
    );
  }

  return (
    <Card className="bg-white shadow-sm border border-gray-100">
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
                onClick={() => setIsOpen(!isOpen)}
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
      
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
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