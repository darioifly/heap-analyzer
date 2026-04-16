import { Crosshair } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useHeapStore } from "@/stores/heapStore";
import { useProjectStore } from "@/stores/projectStore";
import type { Heap } from "@/types";

function SectionHeader({ title }: { title: string }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {title}
    </h3>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-mono">{value}</span>
    </div>
  );
}

interface HeapPropertiesProps {
  heap: Heap;
  onCenterOnMap?: () => void;
}

export function HeapProperties({ heap, onCenterOnMap }: HeapPropertiesProps) {
  const updateHeap = useHeapStore((s) => s.update);
  const project = useProjectStore((s) => s.getSelected());

  const handleLabelChange = (newLabel: string) => {
    updateHeap(heap.id, { label: newLabel || null });
  };

  const handleCategoryChange = (category: string) => {
    updateHeap(heap.id, { materialCategory: category === "__none__" ? null : category });
  };

  return (
    <ScrollArea className="flex-1">
      <div className="p-4 space-y-4">
        {/* Identity */}
        <div className="space-y-3">
          <SectionHeader title="Identità" />
          <MetricRow label="ID" value={`#${heap.id}`} />
          <div className="space-y-1">
            <Label className="text-xs">Etichetta</Label>
            <Input
              defaultValue={heap.label ?? ""}
              placeholder="Senza etichetta"
              className="h-8 text-xs"
              onBlur={(e) => handleLabelChange(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Categoria materiale</Label>
            <Select
              value={heap.materialCategory ?? "__none__"}
              onValueChange={handleCategoryChange}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Non classificato" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Non classificato</SelectItem>
                {(project?.materialCategories ?? []).map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Separator />

        {/* Metrics */}
        <div className="space-y-2">
          <SectionHeader title="Metriche" />
          <MetricRow label="Volume" value={`${heap.volume.toFixed(3)} m³`} />
          <MetricRow label="Area planimetrica" value={`${heap.planimetricArea.toFixed(2)} m²`} />
          <MetricRow label="Area superficiale" value={`${heap.surfaceArea.toFixed(2)} m²`} />
          <MetricRow label="Altezza max" value={`${heap.maxHeight.toFixed(2)} m`} />
          <MetricRow label="Altezza media" value={`${heap.meanHeight.toFixed(2)} m`} />
          <MetricRow label="Quota base" value={`${heap.baseElevation.toFixed(2)} m`} />
        </div>

        <Separator />

        {/* Position */}
        <div className="space-y-2">
          <SectionHeader title="Posizione" />
          <MetricRow label="Centroide E" value={`${heap.centroidE.toFixed(2)}`} />
          <MetricRow label="Centroide N" value={`${heap.centroidN.toFixed(2)}`} />
          <MetricRow label="BBox min" value={`${heap.bboxMinE.toFixed(0)}, ${heap.bboxMinN.toFixed(0)}`} />
          <MetricRow label="BBox max" value={`${heap.bboxMaxE.toFixed(0)}, ${heap.bboxMaxN.toFixed(0)}`} />
        </div>

        <Separator />

        {/* Actions */}
        <div className="space-y-3">
          <SectionHeader title="Azioni" />
          <div className="flex items-center gap-2">
            <Checkbox
              checked={heap.isManuallyConfirmed}
              onCheckedChange={(v) =>
                updateHeap(heap.id, { isManuallyConfirmed: v === true })
              }
              id="confirmed"
            />
            <Label htmlFor="confirmed" className="text-xs">
              Confermato manualmente
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              checked={heap.isExcluded}
              onCheckedChange={(v) =>
                updateHeap(heap.id, { isExcluded: v === true })
              }
              id="excluded"
            />
            <Label htmlFor="excluded" className="text-xs">
              Escludi dal report
            </Label>
          </div>
          {onCenterOnMap && (
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={onCenterOnMap}
            >
              <Crosshair size={14} className="mr-2" strokeWidth={1.75} />
              Centra sulla mappa
            </Button>
          )}
        </div>
      </div>
    </ScrollArea>
  );
}
