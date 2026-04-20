import { useEffect, useState } from "react";
import { Wand2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import type { Settings } from "@/stores/settingsStore";

interface Props {
  draft: Settings;
  onPatch: (patch: Partial<Settings>) => void;
}

interface SchemaField {
  name: string;
  type: string;
  default: unknown;
  description: string;
}

export function ProcessingTab({ draft, onPatch }: Props) {
  const [fields, setFields] = useState<SchemaField[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    window.api.settings
      .getProcessingSchema()
      .then((r) => setFields(r.fields))
      .catch(() => setFields([]))
      .finally(() => setLoading(false));
  }, []);

  const setOverride = (name: string, raw: string, type: string) => {
    let value: number | string | boolean;
    if (type === "int") {
      value = parseInt(raw, 10);
      if (Number.isNaN(value)) return;
    } else if (type === "float") {
      value = parseFloat(raw);
      if (Number.isNaN(value)) return;
    } else if (type === "bool") {
      value = raw === "true";
    } else {
      value = raw;
    }
    onPatch({
      processing: {
        ...draft.processing,
        overrides: { ...draft.processing.overrides, [name]: value },
      },
    });
  };

  const resetOverrides = () => {
    onPatch({
      processing: { ...draft.processing, overrides: {} },
    });
  };

  const detectPython = async () => {
    toast.info(
      "Rilevamento automatico non ancora implementato. Inserire il percorso manualmente.",
    );
  };

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Parametri di default
          </Label>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetOverrides}
            disabled={Object.keys(draft.processing.overrides).length === 0}
          >
            <RotateCcw size={14} className="mr-1.5" strokeWidth={1.75} />
            Ripristina default
          </Button>
        </div>

        {loading && (
          <p className="text-sm text-muted-foreground">Caricamento schema…</p>
        )}
        {!loading && fields.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Schema non disponibile. Il motore Python non risponde.
          </p>
        )}
        {fields.map((f) => {
          const override = draft.processing.overrides[f.name];
          const value = override !== undefined ? String(override) : String(f.default ?? "");
          return (
            <div key={f.name} className="space-y-1">
              <Label htmlFor={`cfg-${f.name}`} className="text-sm">
                {f.name}
                <span className="text-muted-foreground font-normal ml-2">
                  ({f.type}, default {String(f.default)})
                </span>
              </Label>
              <Input
                id={`cfg-${f.name}`}
                value={value}
                onChange={(e) => setOverride(f.name, e.target.value, f.type)}
                placeholder={String(f.default)}
                className="font-mono"
              />
              {f.description && (
                <p className="text-xs text-muted-foreground">{f.description}</p>
              )}
            </div>
          );
        })}
      </div>

      <div className="space-y-2 border-t border-border pt-5">
        <Label>Percorso eseguibile Python</Label>
        <div className="flex gap-2">
          <Input
            value={draft.processing.pythonExecutable || ""}
            onChange={(e) =>
              onPatch({
                processing: { ...draft.processing, pythonExecutable: e.target.value || null },
              })
            }
            placeholder="py -3.11 (default)"
            className="font-mono text-sm"
          />
          <Button variant="outline" onClick={detectPython}>
            <Wand2 size={16} className="mr-2" strokeWidth={1.75} />
            Rileva automaticamente
          </Button>
        </div>
      </div>
    </div>
  );
}
