/**
 * VLM Settings panel — GPU status, model management, models folder.
 *
 * Three sections stacked vertically:
 * 1. GPU status with CUDA/VRAM info
 * 2. Models table with download/load/unload actions
 * 3. Models folder path display
 */

import { useEffect } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Download,
  Trash2,
  Loader2,
  Cpu,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useVlmStore } from '@/stores/vlmStore';
import type { ModelInfo } from '@/stores/vlmStore';

export function VLMSettings() {
  const gpuStatus = useVlmStore((s) => s.gpuStatus);
  const models = useVlmStore((s) => s.models);
  const downloadProgress = useVlmStore((s) => s.downloadProgress);
  const refreshGpuStatus = useVlmStore((s) => s.refreshGpuStatus);
  const refreshModels = useVlmStore((s) => s.refreshModels);
  const downloadModel = useVlmStore((s) => s.downloadModel);
  const cancelDownload = useVlmStore((s) => s.cancelDownload);

  useEffect(() => {
    refreshGpuStatus();
    refreshModels();
  }, [refreshGpuStatus, refreshModels]);

  const vramColorClass = (freeMb: number | null): string => {
    if (freeMb === null) return 'text-muted-foreground';
    if (freeMb >= 16000) return 'text-green-400';
    if (freeMb >= 8000) return 'text-yellow-400';
    return 'text-red-400';
  };

  const modelState = (model: ModelInfo): 'not_downloaded' | 'downloaded' | 'loaded' => {
    // For now, loaded state is tracked locally — will be extended in F4.S03
    if (!model.is_downloaded) return 'not_downloaded';
    return 'downloaded';
  };

  const stateLabel = (state: 'not_downloaded' | 'downloaded' | 'loaded'): string => {
    switch (state) {
      case 'not_downloaded':
        return 'Da scaricare';
      case 'downloaded':
        return 'Scaricato';
      case 'loaded':
        return 'Attivo';
    }
  };

  const stateBadgeVariant = (
    state: 'not_downloaded' | 'downloaded' | 'loaded',
  ): 'secondary' | 'default' | 'outline' => {
    switch (state) {
      case 'not_downloaded':
        return 'secondary';
      case 'downloaded':
        return 'default';
      case 'loaded':
        return 'default';
    }
  };

  return (
    <div className="space-y-6 p-4 max-h-[70vh] overflow-y-auto">
      {/* Section 1 — GPU Status */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold text-foreground mb-3 flex items-center gap-2">
          <Cpu size={18} strokeWidth={1.75} />
          Stato GPU
        </h3>

        {gpuStatus === null ? (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <Loader2 size={14} className="animate-spin" />
            Rilevamento GPU...
          </div>
        ) : gpuStatus.cuda_available ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 size={16} className="text-green-400" />
              <span className="text-foreground">CUDA disponibile</span>
              <span className="text-muted-foreground">— {gpuStatus.device_name}</span>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-muted-foreground">
                VRAM totale:{' '}
                <span className="font-mono text-foreground">
                  {gpuStatus.vram_total_mb !== null
                    ? `${(gpuStatus.vram_total_mb / 1024).toFixed(1)} GB`
                    : '—'}
                </span>
              </span>
              <span className="text-muted-foreground">
                VRAM libera:{' '}
                <span className={`font-mono ${vramColorClass(gpuStatus.vram_free_mb)}`}>
                  {gpuStatus.vram_free_mb !== null
                    ? `${(gpuStatus.vram_free_mb / 1024).toFixed(1)} GB`
                    : '—'}
                </span>
              </span>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2 text-sm">
            <XCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
            <span className="text-muted-foreground">
              GPU CUDA non disponibile. La classificazione automatica non è possibile.
              Usa la classificazione manuale rapida (Ctrl+Shift+C).
            </span>
          </div>
        )}
      </Card>

      {/* Section 2 — Models Table */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold text-foreground mb-3">Modelli VLM</h3>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="text-xs font-semibold uppercase tracking-wider">
                Nome
              </TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider">
                VRAM richiesta
              </TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider">
                Stato
              </TableHead>
              <TableHead className="text-xs font-semibold uppercase tracking-wider text-right">
                Azione
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((model) => {
              const state = modelState(model);
              const progress = downloadProgress[model.name];
              const isDisabled = !gpuStatus?.cuda_available;

              return (
                <TableRow
                  key={model.name}
                  className={isDisabled ? 'opacity-50' : ''}
                >
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{model.display_name}</span>
                      {model.warns_if_insufficient && (
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger>
                              <AlertTriangle size={14} className="text-yellow-400" />
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>VRAM insufficiente sulla GPU corrente</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {model.description}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {(model.vram_required_mb / 1024).toFixed(0)} GB
                  </TableCell>
                  <TableCell>
                    <Badge variant={stateBadgeVariant(state)}>
                      {state === 'loaded' ? (
                        <span className="flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
                          {stateLabel(state)}
                        </span>
                      ) : (
                        stateLabel(state)
                      )}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {progress ? (
                      <div className="flex items-center gap-2 min-w-[200px]">
                        <Progress value={progress.percent} className="flex-1 h-2" />
                        <span className="text-xs text-muted-foreground font-mono w-10 text-right">
                          {progress.percent.toFixed(0)}%
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          onClick={() => cancelDownload(model.name)}
                        >
                          <XCircle size={14} />
                        </Button>
                      </div>
                    ) : state === 'not_downloaded' ? (
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span>
                              <Button
                                variant="default"
                                size="sm"
                                disabled={isDisabled}
                                onClick={() => downloadModel(model.name)}
                              >
                                <Download size={14} className="mr-1" />
                                Scarica
                              </Button>
                            </span>
                          </TooltipTrigger>
                          {isDisabled && (
                            <TooltipContent>
                              <p>GPU non disponibile</p>
                            </TooltipContent>
                          )}
                        </Tooltip>
                      </TooltipProvider>
                    ) : state === 'downloaded' ? (
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" disabled>
                          <Trash2 size={14} className="mr-1" />
                          Elimina
                        </Button>
                      </div>
                    ) : null}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      {/* Section 3 — Models folder */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold text-foreground mb-3">
          Cartella modelli
        </h3>
        <div className="flex items-center gap-3">
          <code className="text-xs text-muted-foreground font-mono bg-muted px-2 py-1 rounded flex-1 truncate">
            {/* Path is resolved by Electron — show a placeholder */}
            %APPDATA%/heap-analyzer/models
          </code>
          <Button variant="ghost" size="sm" disabled>
            Apri cartella
          </Button>
        </div>
      </Card>
    </div>
  );
}
