import { Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import { useMapStore } from "@/stores/mapStore";

export function LayerControls() {
  const {
    ortophotoVisible, ortophotoOpacity,
    heapsVisible, heapsOpacity,
    ndsmVisible, ndsmOpacity,
    labelsVisible,
    setOrtophotoVisible, setOrtophotoOpacity,
    setHeapsVisible, setHeapsOpacity,
    setNdsmVisible, setNdsmOpacity,
    setLabelsVisible,
  } = useMapStore();

  return (
    <Card className="w-64 shadow-md">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Layers size={16} strokeWidth={1.75} />
          Layer
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Ortofoto */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Checkbox
              checked={ortophotoVisible}
              onCheckedChange={(v) => setOrtophotoVisible(v === true)}
              id="layer-ortho"
            />
            <Label htmlFor="layer-ortho" className="text-xs">
              Ortofoto
            </Label>
          </div>
          {ortophotoVisible && (
            <Slider
              value={[ortophotoOpacity]}
              onValueChange={([v]) => setOrtophotoOpacity(v)}
              min={0}
              max={1}
              step={0.05}
              className="ml-6"
            />
          )}
        </div>

        {/* Cumuli */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Checkbox
              checked={heapsVisible}
              onCheckedChange={(v) => setHeapsVisible(v === true)}
              id="layer-heaps"
            />
            <Label htmlFor="layer-heaps" className="text-xs">
              Cumuli
            </Label>
          </div>
          {heapsVisible && (
            <Slider
              value={[heapsOpacity]}
              onValueChange={([v]) => setHeapsOpacity(v)}
              min={0}
              max={1}
              step={0.05}
              className="ml-6"
            />
          )}
        </div>

        {/* nDSM heatmap */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Checkbox
              checked={ndsmVisible}
              onCheckedChange={(v) => setNdsmVisible(v === true)}
              id="layer-ndsm"
            />
            <Label htmlFor="layer-ndsm" className="text-xs">
              Mappa altezze (nDSM)
            </Label>
          </div>
          {ndsmVisible && (
            <Slider
              value={[ndsmOpacity]}
              onValueChange={([v]) => setNdsmOpacity(v)}
              min={0}
              max={1}
              step={0.05}
              className="ml-6"
            />
          )}
        </div>

        {/* Labels toggle */}
        <div className="flex items-center gap-2">
          <Checkbox
            checked={labelsVisible}
            onCheckedChange={(v) => setLabelsVisible(v === true)}
            id="layer-labels"
          />
          <Label htmlFor="layer-labels" className="text-xs">
            Etichette cumuli
          </Label>
        </div>
      </CardContent>
    </Card>
  );
}
