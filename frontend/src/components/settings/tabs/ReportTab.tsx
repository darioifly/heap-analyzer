import { useState, useEffect } from "react";
import { Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Settings } from "@/stores/settingsStore";

interface Props {
  draft: Settings;
  onPatch: (patch: Partial<Settings>) => void;
}

export function ReportTab({ draft, onPatch }: Props) {
  const [logoPreview, setLogoPreview] = useState<string | null>(null);

  useEffect(() => {
    if (draft.report.logoPath) {
      setLogoPreview(`file://${draft.report.logoPath.replace(/\\/g, "/")}`);
    } else {
      setLogoPreview(null);
    }
  }, [draft.report.logoPath]);

  const chooseLogo = async () => {
    const p = await window.api.dialog.openFile({
      title: "Seleziona logo azienda",
      filters: [{ name: "Immagine", extensions: ["png", "jpg", "jpeg"] }],
    });
    if (p) onPatch({ report: { ...draft.report, logoPath: p } });
  };

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label>Logo aziendale</Label>
        <div className="flex items-center gap-3">
          <div className="w-[120px] h-[60px] bg-evlos-900/50 border border-border rounded flex items-center justify-center overflow-hidden">
            {logoPreview ? (
              <img
                src={logoPreview}
                alt="Logo aziendale"
                style={{ maxWidth: "120px", maxHeight: "60px", objectFit: "contain" }}
              />
            ) : (
              <ImageIcon size={24} strokeWidth={1.5} className="text-muted-foreground" />
            )}
          </div>
          <div className="flex flex-col gap-2 flex-1">
            <Input
              value={draft.report.logoPath || ""}
              readOnly
              placeholder="Nessun logo"
              className="font-mono text-xs"
            />
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={chooseLogo}>
                Seleziona…
              </Button>
              {draft.report.logoPath && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onPatch({ report: { ...draft.report, logoPath: null } })}
                >
                  Rimuovi
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <Label>Nome azienda</Label>
        <Input
          value={draft.report.companyName}
          onChange={(e) =>
            onPatch({ report: { ...draft.report, companyName: e.target.value } })
          }
          placeholder="es. IFLY S.r.l."
        />
      </div>

      <div className="space-y-2">
        <Label>Operatore di default</Label>
        <Input
          value={draft.report.defaultOperatorName}
          onChange={(e) =>
            onPatch({ report: { ...draft.report, defaultOperatorName: e.target.value } })
          }
          placeholder="Nome e cognome"
        />
      </div>

      <div className="space-y-2">
        <Label>Piè di pagina personalizzato</Label>
        <Textarea
          value={draft.report.footerText}
          onChange={(e) =>
            onPatch({ report: { ...draft.report, footerText: e.target.value } })
          }
          rows={3}
          placeholder="Testo opzionale stampato sotto ogni pagina del report"
        />
      </div>
    </div>
  );
}
