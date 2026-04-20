/**
 * Top-level error boundary wrapping the main app. Recovers from uncaught
 * render errors by showing a friendly fallback + reload button instead of
 * letting the React tree white-screen.
 */

import { Component, type ReactNode } from "react";
import { AlertTriangle, Copy, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  errorInfo: string | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, errorInfo: null };

  static getDerivedStateFromError(error: Error): State {
    return { error, errorInfo: null };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }): void {
    const stack = info.componentStack || error.stack || "";
    this.setState({ errorInfo: stack });

    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary] uncaught render error:", error, info);

    try {
      window.api?.logging?.rendererError({
        message: error.message,
        stack,
        context: "ErrorBoundary",
      });
    } catch {
      // ignore logging failures — don't cascade
    }
  }

  handleReload = (): void => {
    window.location.reload();
  };

  handleCopy = async (): Promise<void> => {
    const { error, errorInfo } = this.state;
    if (!error) return;
    const payload = [
      `Errore: ${error.message}`,
      "",
      `Stack:\n${error.stack || "(no stack)"}`,
      "",
      `Component stack:\n${errorInfo || "(n/d)"}`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(payload);
    } catch {
      // Fallback: create a textarea + execCommand (legacy path)
      const ta = document.createElement("textarea");
      ta.value = payload;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
  };

  render(): ReactNode {
    const { error, errorInfo } = this.state;
    if (!error) {
      return this.props.children;
    }

    const meta = import.meta as ImportMeta & { env?: { DEV?: boolean } };
    const isDev = Boolean(meta.env?.DEV);

    return (
      <div className="min-h-screen flex items-center justify-center bg-evlos-900 p-8">
        <div className="max-w-2xl w-full bg-evlos-800 border-2 border-red-500 rounded-lg shadow-xl p-8">
          <div className="flex items-start gap-4">
            <AlertTriangle
              size={36}
              strokeWidth={1.75}
              className="text-red-500 shrink-0 mt-1"
            />
            <div className="flex-1 space-y-3">
              <h1 className="text-2xl font-semibold text-foreground font-sans">
                Qualcosa è andato storto
              </h1>
              <p className="text-sm text-muted-foreground">
                I tuoi dati non sono stati persi. Prova a ricaricare l&apos;applicazione.
              </p>
              <div className="mt-4 p-3 bg-evlos-900/60 rounded border border-border font-mono text-sm text-red-300 break-all">
                {error.message}
              </div>

              {isDev && errorInfo && (
                <details className="mt-3 text-xs text-muted-foreground">
                  <summary className="cursor-pointer font-sans">
                    Dettagli tecnici (solo dev)
                  </summary>
                  <pre className="mt-2 p-2 bg-evlos-900/60 rounded border border-border font-mono overflow-x-auto whitespace-pre-wrap">
                    {errorInfo}
                  </pre>
                </details>
              )}

              <div className="flex gap-2 pt-3">
                <Button onClick={this.handleReload}>
                  <RefreshCw size={16} className="mr-2" strokeWidth={1.75} />
                  Ricarica applicazione
                </Button>
                <Button variant="outline" onClick={this.handleCopy}>
                  <Copy size={16} className="mr-2" strokeWidth={1.75} />
                  Copia dettagli
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
