import { useEffect } from "react";
import { useEditingStore } from "@/stores/editingStore";

/**
 * Keyboard shortcuts for editing tools.
 * Active only when the map has focus and no text input is focused.
 *
 * V → Select, P → Draw, M → Modify, X → Split, U → Merge
 * Delete/Backspace → Delete tool
 * Escape → cancel current interaction → return to Select
 * Ctrl+Z → Undo, Ctrl+Shift+Z → Redo
 */
export function useEditingShortcuts(enabled = true): void {
  useEffect(() => {
    if (!enabled) return;

    const handler = (e: KeyboardEvent) => {
      // Bail if a text input / textarea / contentEditable is focused
      const target = e.target as HTMLElement;
      if (
        target.matches(
          'input, textarea, select, [contenteditable="true"]',
        )
      ) {
        return;
      }

      const store = useEditingStore.getState();

      // Ctrl+Z / Ctrl+Shift+Z — undo/redo
      if (e.key === "z" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        if (e.shiftKey) {
          store.redo();
        } else {
          store.undo();
        }
        return;
      }

      // Skip if Ctrl/Alt/Meta is held (except the cases above)
      if (e.ctrlKey || e.altKey || e.metaKey) return;

      switch (e.key.toUpperCase()) {
        case "V":
          e.preventDefault();
          store.setTool("select");
          break;
        case "P":
          e.preventDefault();
          store.setTool("draw");
          break;
        case "M":
          e.preventDefault();
          store.setTool("modify");
          break;
        case "X":
          e.preventDefault();
          store.setTool("split");
          break;
        case "U":
          e.preventDefault();
          store.setTool("merge");
          break;
        case "G":
          e.preventDefault();
          store.setTool("ground-select");
          break;
        case "S":
          e.preventDefault();
          store.setTool("cross-section");
          break;
        case "DELETE":
        case "BACKSPACE":
          e.preventDefault();
          store.setTool("delete");
          break;
        case "ESCAPE":
          e.preventDefault();
          store.setTool("select");
          break;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled]);
}
