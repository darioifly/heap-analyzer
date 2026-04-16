import { Map } from "lucide-react";

export function Viewport() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <Map
        className="text-muted-foreground mb-3"
        size={48}
        strokeWidth={1.75}
      />
      <p className="text-sm text-muted-foreground">
        Importa un rilievo per visualizzare la mappa
      </p>
    </div>
  );
}
