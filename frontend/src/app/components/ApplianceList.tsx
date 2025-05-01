import React from "react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible";
import { ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { Appliance } from "@/types/appliance";
import ApplianceDialog from "./ApplianceDialog";

const APPLIANCE_TYPES = [
  {
    type: "CONSTANT",
    title: "Konstantní spotřeba",
    description: "Neměnná spotřeba energie, běží nepřetržitě",
  },
  {
    type: "CYCLIC",
    title: "Cyklická spotřeba",
    description: "Střídá fáze běhu a pohotovostního režimu",
  },
  {
    type: "SCHEDULED",
    title: "Plánovaná spotřeba",
    description: "Spouští se v definovaných časových oknech",
  },
  {
    type: "ON_DEMAND",
    title: "Spotřeba na vyžádání",
    description: "Nepravidelné používání během dne",
  },
] as const;

interface ApplianceListProps {
  appliances: Appliance[];
  houseId: number;
  onSuccess: () => void;
  onDelete: (id: number) => void;
}

interface TypeSectionProps {
  type: string;
  title: string;
  description: string;
  appliances: Appliance[];
  houseId: number;
  onSuccess: () => void;
  onDelete: (id: number) => void;
}

const TypeSection: React.FC<TypeSectionProps> = ({
  type,
  title,
  description,
  appliances,
  houseId,
  onSuccess,
  onDelete,
}) => {
  const [isOpen, setIsOpen] = React.useState<boolean>(false);
  const appliancesOfType = appliances.filter(
    (a: Appliance) => a.appliance_type === type
  );

  if (appliancesOfType.length === 0) return null;

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-4 cursor-pointer" onClick={() => setIsOpen(!isOpen)}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-medium text-gray-900">{title}</h3>
              <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                {appliancesOfType.length}
              </span>
            </div>
            <p className="text-sm text-gray-600">{description}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen(!isOpen);
            }}
          >
            {isOpen ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
      <Collapsible open={isOpen}>
        <CollapsibleContent>
          <div className="px-4 pb-4 border-t border-gray-100 pt-4">
            <div className="space-y-3">
              {appliancesOfType.map((appliance) => (
                <div
                  key={appliance.id}
                  className="flex justify-between items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div>
                    <h4 className="font-medium text-gray-900">
                      {appliance.name}
                    </h4>
                    <p className="text-sm text-gray-600">
                      Spotřeba: {appliance.power_consumption.toString()} W
                      {appliance.standby_power
                        ? ` | Standby: ${appliance.standby_power} W`
                        : ""}
                    </p>
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
              ))}
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
};

const ApplianceList: React.FC<ApplianceListProps> = ({
  appliances,
  houseId,
  onSuccess,
  onDelete,
}) => {
  if (appliances.length === 0) {
    return (
      <Card className="bg-white shadow-sm border border-gray-100">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-xl font-semibold text-gray-900">
              Spotřebiče
            </CardTitle>
            <ApplianceDialog houseId={houseId} onSuccess={onSuccess} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center p-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200">
            <p className="text-gray-500 mb-4">
              Zatím nejsou přidány žádné spotřebiče
            </p>
            <ApplianceDialog houseId={houseId} onSuccess={onSuccess} />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white shadow-sm border border-gray-100">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl font-semibold text-gray-900">
            Spotřebiče ({appliances.length})
          </CardTitle>
          <ApplianceDialog houseId={houseId} onSuccess={onSuccess} />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {APPLIANCE_TYPES.map((type) => (
            <TypeSection
              key={type.type}
              {...type}
              appliances={appliances}
              houseId={houseId}
              onSuccess={onSuccess}
              onDelete={onDelete}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export default ApplianceList;
