import { FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { VLMSettings } from "../VLMSettings";
import type { Settings } from "@/stores/settingsStore";

interface Props {
  draft: Settings;
  onPatch: (patch: Partial<Settings>) => void;
}

export function VLMTab({ draft, onPatch }: Props) {
  const chooseModelsDir = async () => {
    const dir = await window.api.dialog.openDirectory({
      title: "Cartella modelli VLM",
    });
    if (dir) onPatch({ vlm: { ...draft.vlm, modelsDir: dir } });
  };

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label>Cartella modelli VLM</Label>
        <div className="flex gap-2">
          <Input
            value={draft.vlm.modelsDir || ""}
            readOnly
            placeholder="Percorso di default (userData/models)"
            className="font-mono text-sm"
          />
          <Button variant="outline" onClick={chooseModelsDir}>
            <FolderOpen size={16} className="mr-2" strokeWidth={1.75} />
            Sfoglia…
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <Label>VRAM disponibile stimata (GB)</Label>
        <div className="flex items-center gap-4">
          <Slider
            min={2}
            max={24}
            step={1}
            value={[draft.vlm.estimatedVramGb]}
            onValueChange={(v) =>
              onPatch({ vlm: { ...draft.vlm, estimatedVramGb: v[0] ?? 8 } })
            }
            className="flex-1"
          />
          <span className="font-mono text-sm w-10 text-right">
            {draft.vlm.estimatedVramGb}
          </span>
        </div>
      </div>

      <div className="border-t border-border pt-5">
        <Label className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Modelli installati
        </Label>
        <div className="mt-3">
          <VLMSettings />
        </div>
      </div>
    </div>
  );
}
