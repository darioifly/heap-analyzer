import React, { useState } from 'react';
import './App.css';

interface ProgressMessage {
  type: 'progress';
  phase: string;
  percent: number;
  message: string;
}

interface ResultMessage {
  type: 'result';
  data: Record<string, unknown>;
}

type PythonMessage = ProgressMessage | ResultMessage | { type: 'error' | 'warning'; message: string };

function App(): React.ReactElement {
  const [messages, setMessages] = useState<PythonMessage[]>([]);
  const [running, setRunning] = useState(false);

  const handleTestPython = async (): Promise<void> => {
    setMessages([]);
    setRunning(true);

    try {
      const api = (window as unknown as { api: { python: { execute: (cmd: string, args: string[]) => Promise<ResultMessage>; onProgress: (cb: (data: ProgressMessage) => void) => void } } }).api;

      api.python.onProgress((data: ProgressMessage) => {
        setMessages((prev) => [...prev, data]);
      });

      const result = await api.python.execute('process', [
        '--las', 'test',
        '--tiff', 'test',
        '--output', 'test',
      ]);
      setMessages((prev) => [...prev, result]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { type: 'error', message: String(err) },
      ]);
    } finally {
      setRunning(false);
    }
  };

  const handleCancel = async (): Promise<void> => {
    const api = (window as unknown as { api: { python: { cancel: () => Promise<void> } } }).api;
    await api.python.cancel();
    setRunning(false);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Heap Analyzer — v0.1.0</h1>
        <p className="subtitle">Analisi volumetrica cumuli da nuvole di punti LiDAR</p>
      </header>

      <main className="app-main">
        <div className="button-group">
          <button onClick={handleTestPython} disabled={running} className="btn-primary">
            {running ? 'Elaborazione...' : 'Test Python Bridge'}
          </button>
          {running && (
            <button onClick={handleCancel} className="btn-danger">
              Annulla
            </button>
          )}
        </div>

        {messages.length > 0 && (
          <pre className="output-box">
            {messages.map((m) => JSON.stringify(m, null, 2)).join('\n---\n')}
          </pre>
        )}
      </main>
    </div>
  );
}

export default App;
