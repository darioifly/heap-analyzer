import { useState, useMemo } from "react";
import { ArrowDownUp, CheckCircle2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { useHeapStore } from "@/stores/heapStore";
import type { Heap } from "@/types";

const CATEGORY_COLORS: Record<string, string> = {
  "Rottame ferroso": "#B45309",
  Ghisa: "#6575A0",
  Scorie: "#6B7280",
  Cascami: "#92400E",
  RAEE: "#059669",
};
const DEFAULT_COLOR = "#6575A0";

type SortKey = "id" | "volume" | "area" | "height" | "category";

const SORT_LABELS: Record<SortKey, string> = {
  id: "Per ID",
  volume: "Per volume (decrescente)",
  area: "Per area",
  height: "Per altezza",
  category: "Per categoria",
};

function sortHeaps(heaps: Heap[], key: SortKey): Heap[] {
  const sorted = [...heaps];
  switch (key) {
    case "id":
      return sorted.sort((a, b) => a.id - b.id);
    case "volume":
      return sorted.sort((a, b) => b.volume - a.volume);
    case "area":
      return sorted.sort((a, b) => b.planimetricArea - a.planimetricArea);
    case "height":
      return sorted.sort((a, b) => b.maxHeight - a.maxHeight);
    case "category":
      return sorted.sort((a, b) =>
        (a.materialCategory ?? "zzz").localeCompare(b.materialCategory ?? "zzz"),
      );
  }
}

interface HeapListProps {
  heaps: Heap[];
  onSelect: (heapId: number) => void;
}

export function HeapList({ heaps, onSelect }: HeapListProps) {
  const selectedHeapId = useHeapStore((s) => s.selectedHeapId);
  const [sortKey, setSortKey] = useState<SortKey>("volume");
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    const lower = filter.toLowerCase();
    const f = heaps.filter((h) => {
      const text = `${h.label ?? ""} ${h.materialCategory ?? ""} #${h.id}`.toLowerCase();
      return text.includes(lower);
    });
    return sortHeaps(f, sortKey);
  }, [heaps, filter, sortKey]);

  if (heaps.length === 0) return null;

  return (
    <>
      <Separator />
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Cumuli ({filtered.length})
        </h2>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7">
              <ArrowDownUp size={14} strokeWidth={1.75} />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
              <DropdownMenuItem
                key={key}
                onClick={() => setSortKey(key)}
                className={cn(sortKey === key && "font-semibold")}
              >
                {SORT_LABELS[key]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="px-3 py-2">
        <div className="relative">
          <Search
            size={12}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filtra..."
            className="h-7 text-xs pl-7"
          />
        </div>
      </div>

      <ScrollArea className="flex-1 max-h-[300px]">
        <div className="py-1">
          {filtered.map((heap) => {
            const color =
              (heap.materialCategory && CATEGORY_COLORS[heap.materialCategory]) ||
              DEFAULT_COLOR;
            const isSelected = heap.id === selectedHeapId;

            return (
              <div
                key={heap.id}
                className={cn(
                  "flex items-center gap-2 px-4 py-1.5 cursor-pointer transition-colors",
                  "hover:bg-accent dark:hover:bg-evlos-700",
                  isSelected && "bg-primary/10 border-l-2 border-l-primary",
                  heap.isExcluded && "opacity-50",
                )}
                onClick={() => onSelect(heap.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") onSelect(heap.id);
                }}
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: color }}
                />
                <div className="flex-1 min-w-0">
                  <p
                    className={cn(
                      "text-xs font-medium truncate",
                      heap.isExcluded && "line-through",
                    )}
                  >
                    {heap.label || `#${heap.id}`}
                  </p>
                  <p className="text-xs font-mono text-muted-foreground">
                    {heap.volume.toFixed(2)} m³
                  </p>
                </div>
                {heap.isManuallyConfirmed && (
                  <CheckCircle2
                    size={14}
                    className="text-success-500 shrink-0"
                    strokeWidth={1.75}
                  />
                )}
              </div>
            );
          })}
        </div>
      </ScrollArea>
    </>
  );
}
