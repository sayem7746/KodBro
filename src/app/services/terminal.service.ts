import { Injectable, NgZone } from '@angular/core';

export interface TerminalLine {
  type: 'command' | 'output' | 'error' | 'prompt';
  text: string;
}

export interface TerminalConnection {
  connected: boolean;
  serverUrl: string;
  isRemoteApi: boolean;
}

interface RunCommandResponse {
  ok: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out?: boolean;
}

/**
 * Terminal service: connects to either
 * - WebSocket (ws://) for local interactive PTY, or
 * - Remote HTTP API (https://) e.g. Vercel for one-off commands.
 */
@Injectable({ providedIn: 'root' })
export class TerminalService {
  private output: TerminalLine[] = [];
  private commandHistory: string[] = [];
  private historyIndex = -1;
  private ws: WebSocket | null = null;
  private _serverUrl = 'https://agent.kodbro.com';
  private _connected = false;
  private _isRemoteApi = false;
  private outputBuffer = '';

  constructor(private ngZone: NgZone) {}

  get lines(): TerminalLine[] {
    return [...this.output];
  }

  get connection(): TerminalConnection {
    return { connected: this._connected, serverUrl: this._serverUrl, isRemoteApi: this._isRemoteApi };
  }

  get prompt(): string {
    return this._connected ? '' : 'kodbro$ ';
  }

  get serverUrl(): string {
    return this._serverUrl;
  }

  set serverUrl(url: string) {
    this._serverUrl = (url || '').trim() || 'https://agent.kodbro.com';
  }

  private isHttpUrl(url: string): boolean {
    const u = url.toLowerCase();
    return u.startsWith('http://') || u.startsWith('https://');
  }

  connect(serverUrl?: string): void {
    const url = (serverUrl ?? this._serverUrl).trim() || this._serverUrl;
    this._serverUrl = url;

    if (this.isHttpUrl(url)) {
      this.connectRemoteApi(url);
    } else {
      this.connectWebSocket(url);
    }
  }

  private connectRemoteApi(baseUrl: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.close();
      this.ws = null;
    }
    const apiBase = baseUrl.replace(/\/+$/, '');
    this._serverUrl = apiBase;
    this._connected = true;
    this._isRemoteApi = true;
    this.appendOutput('output', `Connected to remote API: ${apiBase}`);
    this.appendOutput('output', 'Type commands below (each runs via POST /api/run).');
  }

  private connectWebSocket(url: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    this._isRemoteApi = false;
    this.appendOutput('output', `Connecting to ${url}...`);
    try {
      this.ws = new WebSocket(url);
      this.ws.binaryType = 'arraybuffer';
      this.ws.onopen = () => {
        this.ngZone.run(() => {
          this._connected = true;
          this.outputBuffer = '';
          this.appendOutput('output', 'Connected. Type commands below.');
        });
      };
      this.ws.onmessage = (event: MessageEvent) => {
        const text = typeof event.data === 'string' ? event.data : new TextDecoder().decode(event.data);
        this.ngZone.run(() => this.flushOutput(text));
      };
      this.ws.onerror = () => {
        this.ngZone.run(() => this.appendOutput('error', 'WebSocket error.'));
      };
      this.ws.onclose = () => {
        this.ngZone.run(() => {
          this._connected = false;
          this.ws = null;
          this.appendOutput('output', 'Disconnected from server.');
        });
      };
    } catch (e) {
      this._connected = false;
      this.appendOutput('error', `Failed to connect: ${e}`);
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._connected = false;
    this._isRemoteApi = false;
    this.appendOutput('output', 'Disconnected.');
  }

  executeCommand(raw: string): void {
    const cmd = raw.trim();
    if (!cmd) return;

    if (cmd === 'clear' || cmd === 'cls') {
      this.output = [];
      return;
    }

    this.commandHistory.push(cmd);
    this.historyIndex = this.commandHistory.length;

    if (!this._connected) {
      this.appendOutput('output', 'Not connected. Enter server URL and tap Connect.');
      return;
    }

    this.appendOutput('command', cmd);

    if (this._isRemoteApi) {
      this.runViaRemoteApi(cmd);
    } else if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(cmd + '\n');
    }
  }

  private runViaRemoteApi(command: string): void {
    const apiBase = this._serverUrl.replace(/\/+$/, '');
    const url = `${apiBase}/api/run`;
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, timeout_seconds: 10 }),
    })
      .then((res) => res.json() as Promise<RunCommandResponse>)
      .then((data) => {
        this.ngZone.run(() => {
          if (data.stdout) {
            data.stdout.split(/\n/).forEach((line) => this.appendOutput('output', line));
          }
          if (data.stderr) {
            data.stderr.split(/\n/).forEach((line) => this.appendOutput('error', line));
          }
          if (data.timed_out) {
            this.appendOutput('error', 'Command timed out.');
          }
        });
      })
      .catch((err) => {
        this.ngZone.run(() =>
          this.appendOutput('error', `Request failed: ${err?.message || 'Network error'}. Check URL and CORS.`)
        );
      });
  }

  getHistory(direction: 'prev' | 'next'): string | null {
    if (this.commandHistory.length === 0) return null;
    if (direction === 'prev') {
      this.historyIndex = Math.max(-1, this.historyIndex - 1);
      return this.historyIndex === -1 ? '' : this.commandHistory[this.historyIndex];
    }
    this.historyIndex = Math.min(this.commandHistory.length, this.historyIndex + 1);
    return this.historyIndex === this.commandHistory.length ? '' : this.commandHistory[this.historyIndex];
  }

  clear(): void {
    this.output = [];
  }

  private flushOutput(chunk: string): void {
    this.outputBuffer += chunk;
    const lines = this.outputBuffer.split(/\n/);
    if (lines.length > 1) {
      this.outputBuffer = lines.pop() ?? '';
      for (const line of lines) {
        this.appendOutput('output', line);
      }
    }
    if (this.outputBuffer && !chunk.endsWith('\n')) {
      return;
    }
    if (this.outputBuffer) {
      this.appendOutput('output', this.outputBuffer.replace(/\r$/, ''));
      this.outputBuffer = '';
    }
  }

  private appendOutput(type: TerminalLine['type'], text: string): void {
    if (text) this.output.push({ type, text });
  }
}
