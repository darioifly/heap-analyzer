/**
 * Full-screen settings modal with 4 tabs: Generali, Processing, VLM, Report.
 *
 * Behavior:
 *  - Opens on gear icon click (HeaderBar).
 *  - Stages edits in a local draft; commits via "Salva" or discards via
 *    "Annulla" / ESC with a nested confirmation if dirty.
 *  - Persists through `window.api.settings.*` which writes atomically under
 *    userData/settings.json.
 */

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { useSettingsStore, defaultSettings, type Settings } from "@/stores/settingsStore";
import { GeneralTab } from "./tabs/GeneralTab";
import { ProcessingTab } from "./tabs/ProcessingTab";
import { VLMTab } from "./tabs/VLMTab";
import { ReportTab } from "./tabs/ReportTab";

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const settings = useSettingsStore((s) => s.settings);
  const loaded = useSettingsStore((s) => s.loaded);
  const loadFromDisk = useSettingsStore((s) => s.loadFromDisk);
  const save = useSettingsStore((s) => s.save);
  const saving = useSettingsStore((s) => s.saving);

  const [draft, setDraft] = useState<Settings>(defaultSettings);
  const [confirmDiscardOpen, setConfirmDiscardOpen] = useState(false);

  // Load on first mount
  useEffect(() => {
    if (!loaded) {
      void loadFromDisk();
    }
  }, [loaded, loadFromDisk]);

  // Re-seed draft whenever modal opens
  useEffect(() => {
    if (open) {
      setDraft(settings);
    }
  }, [open, settings]);

  const isDirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(settings),
    [draft, settings],
  );

  const patch = (p: Partial<Settings>) => {
    setDraft((cur) => ({ ...cur, ...p }));
  };

  const tryClose = (next: boolean) => {
    if (!next && isDirty) {
      setConfirmDiscardOpen(true);
      return;
    }
    onOpenChange(next);
  };

  const discardAndClose = () => {
    setConfirmDiscardOpen(false);
    setDraft(settings);
    onOpenChange(false);
  };

  const onSave = async () => {
    try {
      await save(draft);
      toast.success("Impostazioni salvate");
      onOpenChange(false);
    } catch (err) {
      toast.error(
        `Errore salvataggio: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={tryClose}>
        <DialogContent
          className="max-w-[90vw] w-[90vw] h-[85vh] max-h-[85vh] flex flex-col p-0 gap-0"
          onEscapeKeyDown={(e) => {
            if (isDirty) {
              e.preventDefault();
              setConfirmDiscardOpen(true);
            }
          }}
        >
          <DialogHeader className="px-6 pt-6 pb-3 border-b border-border shrink-0">
            <DialogTitle className="text-xl">Impostazioni</DialogTitle>
          </DialogHeader>

          <Tabs defaultValue="general" className="flex-1 flex flex-col overflow-hidden">
            <TabsList className="mx-6 mt-4 self-start">
              <TabsTrigger value="general">Generali</TabsTrigger>
              <TabsTrigger value="processing">Processing</TabsTrigger>
              <TabsTrigger value="vlm">VLM</TabsTrigger>
              <TabsTrigger value="report">Report</TabsTrigger>
            </TabsList>
            <div className="flex-1 overflow-y-auto px-6 py-4">
              <TabsContent value="general">
                <GeneralTab draft={draft} onPatch={patch} />
              </TabsContent>
              <TabsContent value="processing">
                <ProcessingTab draft={draft} onPatch={patch} />
              </TabsContent>
              <TabsContent value="vlm">
                <VLMTab draft={draft} onPatch={patch} />
              </TabsContent>
              <TabsContent value="report">
                <ReportTab draft={draft} onPatch={patch} />
              </TabsContent>
            </div>
          </Tabs>

          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border shrink-0">
            <Button variant="outline" onClick={() => tryClose(false)} disabled={saving}>
              Annulla
            </Button>
            <Button onClick={onSave} disabled={!isDirty || saving}>
              Salva
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmDiscardOpen} onOpenChange={setConfirmDiscardOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Modifiche non salvate</AlertDialogTitle>
            <AlertDialogDescription>
              Sono presenti modifiche non salvate. Vuoi davvero chiudere?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Continua a modificare</AlertDialogCancel>
            <AlertDialogAction onClick={discardAndClose}>
              Scarta modifiche
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
