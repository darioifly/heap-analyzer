/**
 * Settings dialog — triggered by the gear icon in the header.
 *
 * Currently contains VLM settings. Will be extended with additional
 * settings sections in F7.S02.
 */

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { VLMSettings } from './VLMSettings';

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Impostazioni</DialogTitle>
        </DialogHeader>
        <VLMSettings />
      </DialogContent>
    </Dialog>
  );
}
