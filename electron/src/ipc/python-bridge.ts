import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';

/** A JSON Lines message from the Python engine. Every message has a 'type'. */
export interface PythonMessage {
  type: 'progress' | 'result' | 'error' | 'warning';
  [key: string]: unknown;
}

export interface ProgressMessage extends PythonMessage {
  type: 'progress';
  phase: string;
  percent: number;
  message: string;
}

export interface ResultMessage extends PythonMessage {
  type: 'result';
  data: Record<string, unknown>;
}

export interface ErrorMessage extends PythonMessage {
  type: 'error';
  code: string;
  message: string;
}

export interface WarningMessage extends PythonMessage {
  type: 'warning';
  message: string;
}

/** Default timeout: 30 minutes in milliseconds. */
const DEFAULT_TIMEOUT_MS = 30 * 60 * 1000;

/**
 * Parse a raw stdout buffer into individual JSON Lines messages.
 *
 * Handles:
 * - Partial lines (data arriving in chunks)
 * - Windows UTF-8 BOM (\xEF\xBB\xBF)
 * - Empty lines (skipped)
 * - Non-JSON lines (emitted as warnings)
 *
 * @param buffer Accumulated string buffer (may be modified on return)
 * @param chunk  New data chunk to append
 * @returns [parsed messages, updated buffer]
 */
export function parseJsonLines(
  buffer: string,
  chunk: string,
): [PythonMessage[], string] {
  // Strip UTF-8 BOM if present at the very beginning
  let data = chunk;
  if (buffer === '' && data.startsWith('\uFEFF')) {
    data = data.slice(1);
  }

  const combined = buffer + data;
  const lines = combined.split('\n');

  // Last element may be an incomplete line — keep it in buffer
  const remaining = lines.pop() ?? '';
  const messages: PythonMessage[] = [];

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue; // skip empty lines

    try {
      const obj = JSON.parse(line) as Record<string, unknown>;
      if (typeof obj.type !== 'string') {
        // Has no 'type' field — treat as malformed, emit warning
        messages.push({
          type: 'warning',
          message: `Python stdout line missing 'type': ${line.slice(0, 200)}`,
        });
        continue;
      }
      const validTypes = new Set(['progress', 'result', 'error', 'warning']);
      if (!validTypes.has(obj.type as string)) {
        messages.push({
          type: 'warning',
          message: `Python stdout has unknown type '${obj.type}': ${line.slice(0, 200)}`,
        });
        continue;
      }
      messages.push(obj as PythonMessage);
    } catch {
      // Non-JSON line on stdout — protocol violation, report as warning
      messages.push({
        type: 'warning',
        message: `Non-JSON on Python stdout (protocol violation): ${line.slice(0, 200)}`,
      });
    }
  }

  return [messages, remaining];
}

/**
 * Manages a Python subprocess, parses its JSON Lines stdout, and emits typed events.
 *
 * Events:
 *   'progress'  — ProgressMessage
 *   'result'    — ResultMessage
 *   'error'     — ErrorMessage
 *   'warning'   — WarningMessage
 *   'exit'      — { code: number | null }
 */
export class PythonBridge extends EventEmitter {
  private process: ChildProcess | null = null;
  private timeoutHandle: ReturnType<typeof setTimeout> | null = null;
  private readonly timeoutMs: number;

  constructor(timeoutMs: number = DEFAULT_TIMEOUT_MS) {
    super();
    this.timeoutMs = timeoutMs;
  }

  /**
   * Spawn the heap-analyzer CLI and return a promise that resolves with the
   * final ResultMessage or rejects with an ErrorMessage.
   */
  execute(command: string, args: string[]): Promise<ResultMessage> {
    return new Promise((resolve, reject) => {
      const cliArgs = [command, ...args];
      let stdoutBuffer = '';
      let result: ResultMessage | null = null;

      // Find heap-analyzer — assumes it's on PATH (installed via pip install -e .)
      const executable = process.platform === 'win32' ? 'heap-analyzer.exe' : 'heap-analyzer';

      this.process = spawn(executable, cliArgs, {
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
      });

      // stdout → JSON Lines parser
      this.process.stdout?.setEncoding('utf8');
      this.process.stdout?.on('data', (chunk: string) => {
        const [messages, remaining] = parseJsonLines(stdoutBuffer, chunk);
        stdoutBuffer = remaining;
        for (const msg of messages) {
          this.emit(msg.type, msg);
          if (msg.type === 'result') {
            result = msg as ResultMessage;
          }
        }
      });

      // stderr → log to console.error (never to stdout)
      this.process.stderr?.setEncoding('utf8');
      this.process.stderr?.on('data', (chunk: string) => {
        console.error('[python-engine]', chunk.trim());
      });

      // Set timeout
      this.timeoutHandle = setTimeout(() => {
        this.emit('warning', {
          type: 'warning',
          message: `Python process timed out after ${this.timeoutMs / 1000}s — killing`,
        } satisfies WarningMessage);
        this.kill();
        reject(new Error('Python process timed out'));
      }, this.timeoutMs);

      this.process.on('close', (code) => {
        this.clearTimeout();
        this.process = null;
        this.emit('exit', { code });

        if (result) {
          resolve(result);
        } else if (code === 0) {
          reject(new Error('Python process exited 0 but emitted no result message'));
        } else {
          reject(new Error(`Python process exited with code ${code}`));
        }
      });

      this.process.on('error', (err) => {
        this.clearTimeout();
        reject(err);
      });
    });
  }

  /** Cancel the running process: SIGTERM → wait 5s → SIGKILL. */
  cancel(): void {
    if (!this.process) return;
    this.clearTimeout();

    if (process.platform === 'win32') {
      // Windows does not have SIGTERM for child_process.kill — use taskkill
      this.kill();
      return;
    }

    this.process.kill('SIGTERM');
    const killTimer = setTimeout(() => {
      this.kill();
    }, 5000);
    this.process.once('close', () => clearTimeout(killTimer));
  }

  private kill(): void {
    if (this.process) {
      this.process.kill('SIGKILL');
    }
  }

  private clearTimeout(): void {
    if (this.timeoutHandle !== null) {
      clearTimeout(this.timeoutHandle);
      this.timeoutHandle = null;
    }
  }
}
