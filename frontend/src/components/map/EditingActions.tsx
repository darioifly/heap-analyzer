import { useEffect, useState, useCallback } from "react";
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
import { toast } from "sonner";
import { useEditingStore } from "@/stores/editingStore";
import { useHeapStore } from "@/stores/heapStore";
import type { Heap } from "@/types";

interface EditingActionsProps {
  surveyId: number;
}

/**
 * Handles delete confirmation dialog and merge execution.
 * Renders only the AlertDialog UI — logic is triggered by store state changes.
 */
export function EditingActions({ surveyId }: EditingActionsProps) {
  const [deleteTarget, setDeleteTarget] = useState<Heap | null>(null);
  const activeTool = useEditingStore((s) => s.activeTool);
  const pushHistory = useEditingStore((s) => s.pushHistory);
  const mergeSelection = useEditingStore((s) => s.mergeSelection);
  const selectedHeapId = useHeapStore((s) => s.selectedHeapId);
  const heaps = useHeapStore((s) => s.heaps);
  const loadBySurvey = useHeapStore((s) => s.loadBySurvey);

  const refreshHeaps = useCallback(async () => {
    await loadBySurvey(surveyId);
  }, [loadBySurvey, surveyId]);

  // When delete tool is active and a heap is selected, show confirm dialog
  useEffect(() => {
    if (activeTool === "delete" && selectedHeapId != null) {
      const heap = heaps.find((h) => h.id === selectedHeapId);
      if (heap) {
        setDeleteTarget(heap);
      }
    }
  }, [activeTool, selectedHeapId, heaps]);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    const beforeHeaps = [deleteTarget];

    try {
      await window.api.editing.deleteHeap({ heapId: deleteTarget.id });
      toast.success(
        `Cumulo "${deleteTarget.label || `#${deleteTarget.id}`}" eliminato`,
      );
      await refreshHeaps();

      pushHistory({
        op: "delete",
        timestamp: Date.now(),
        before: beforeHeaps,
        after: [],
        surveyId,
      });
    } catch (err) {
      toast.error(
        `Errore: ${err instanceof Error ? err.message : String(err)}`,
        { duration: 6000 },
      );
    }

    setDeleteTarget(null);
    useEditingStore.getState().setTool("select");
    useHeapStore.getState().select(null);
  }, [deleteTarget, surveyId, pushHistory, refreshHeaps]);

  const handleCancelDelete = useCallback(() => {
    setDeleteTarget(null);
    useEditingStore.getState().setTool("select");
  }, []);

  // Merge action — triggered externally via store
  const handleMerge = useCallback(async () => {
    if (mergeSelection.length < 2) return;

    const beforeHeaps = heaps.filter((h) =>
      mergeSelection.includes(h.id),
    );

    try {
      const merged = await window.api.editing.mergeHeaps({
        heapIds: mergeSelection,
        surveyId,
      });
      const volume = (merged as unknown as { volume: number }).volume ?? 0;
      toast.success(
        `${mergeSelection.length} cumuli uniti — volume: ${volume.toFixed(2)} m³`,
        { className: "font-mono" },
      );

      await refreshHeaps();

      pushHistory({
        op: "merge",
        timestamp: Date.now(),
        before: beforeHeaps,
        after: [merged as unknown as Heap],
        surveyId,
      });

      useEditingStore.getState().clearMergeSelection();
      useEditingStore.getState().setTool("select");
    } catch (err) {
      toast.error(
        `Errore: ${err instanceof Error ? err.message : String(err)}`,
        { duration: 6000 },
      );
    }
  }, [mergeSelection, heaps, surveyId, pushHistory, refreshHeaps]);

  // Expose merge handler via a global ref that the toolbar can call
  useEffect(() => {
    (window as unknown as { __heapMerge: () => void }).__heapMerge =
      handleMerge;
  }, [handleMerge]);

  return (
    <AlertDialog
      open={deleteTarget !== null}
      onOpenChange={(open) => {
        if (!open) handleCancelDelete();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Elimina cumulo</AlertDialogTitle>
          <AlertDialogDescription>
            Eliminare definitivamente il cumulo &quot;
            {deleteTarget?.label || `#${deleteTarget?.id}`}&quot;? Questa
            azione può essere annullata con Ctrl+Z.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annulla</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDelete}
            className="bg-danger-600 hover:bg-danger-700 text-white"
          >
            Elimina
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
