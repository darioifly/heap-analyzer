import { FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { Settings } from "@/stores/settingsStore";

interface Props {
  draft: Settings;
  onPatch: (patch: Partial<Settings>) => void;
}

export function GeneralTab({ draft, onPatch }: Props) {
  const chooseDir = async () => {
    const dir = await window.api.dialog.openDirectory({
      title: "Cartella dati di default",
    });
    if (dir) onPatch({ general: { ...draft.general, dataDir: dir } });
  };

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label>Cartella dati di default</Label>
        <div className="flex gap-2">
          <Input
            value={draft.general.dataDir || ""}
            readOnly
            placeholder="Non impostata"
            className="font-mono text-sm"
          />
          <Button variant="outline" onClick={chooseDir}>
            <FolderOpen size={16} className="mr-2" strokeWidth={1.75} />
            Sfoglia…
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <Label>Lingua interfaccia</Label>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <Select value={draft.general.language} disabled>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="it">Italiano</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </TooltipTrigger>
            <TooltipContent>Altre lingue in arrivo</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      <div className="space-y-2">
        <Label>Tema</Label>
        <Select
          value={draft.general.theme}
          onValueChange={(v) =>
            onPatch({ general: { ...draft.general, theme: v as "dark" | "light" } })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="dark">Scuro</SelectItem>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div>
                    <SelectItem value="light" disabled>
                      Chiaro
                    </SelectItem>
                  </div>
                </TooltipTrigger>
                <TooltipContent>Non ancora supportato</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
