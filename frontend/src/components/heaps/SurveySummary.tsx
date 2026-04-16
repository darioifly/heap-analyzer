import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { Survey, Heap } from "@/types";

function SectionHeader({ title }: { title: string }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
      {title}
    </h3>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-mono">{value}</span>
    </div>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function basename(p: string): string {
  return p.replace(/^.*[\\/]/, "");
}

interface SurveySummaryProps {
  survey: Survey;
  heaps: Heap[];
}

export function SurveySummary({ survey, heaps }: SurveySummaryProps) {
  const totalVolume = heaps.reduce((sum, h) => sum + h.volume, 0);
  const avgVolume = heaps.length > 0 ? totalVolume / heaps.length : 0;
  const largest = heaps.length > 0
    ? heaps.reduce((a, b) => (a.volume > b.volume ? a : b))
    : null;

  return (
    <ScrollArea className="flex-1">
      <div className="p-4 space-y-4">
        <div className="space-y-2">
          <SectionHeader title="Rilievo" />
          <InfoRow label="Data" value={formatDate(survey.surveyDate)} />
          <InfoRow label="Operatore" value={survey.operator ?? "—"} />
          <InfoRow label="File LAS" value={basename(survey.lasPath)} />
          <InfoRow label="File ortofoto" value={basename(survey.tiffPath)} />
        </div>

        {survey.processingStatus === "completed" && (
          <>
            <Separator />
            <div className="space-y-2">
              <SectionHeader title="Risultati elaborazione" />
              <InfoRow label="N. cumuli rilevati" value={`${heaps.length}`} />
              <InfoRow label="Volume totale" value={`${totalVolume.toFixed(2)} m³`} />
              <InfoRow label="Volume medio" value={`${avgVolume.toFixed(2)} m³`} />
              {largest && (
                <InfoRow
                  label="Cumulo più grande"
                  value={`#${largest.id} — ${largest.volume.toFixed(2)} m³`}
                />
              )}
            </div>
          </>
        )}
      </div>
    </ScrollArea>
  );
}
