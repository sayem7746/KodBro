import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';

const DEFAULT_API_BASE = 'https://agent.kodbro.com';

export type AgentLogEvent =
  | { type: 'log'; message: string; level?: string }
  | { type: 'done'; reply: string; tool_summary?: string[] }
  | { type: 'error'; error: string };

export interface GitConnection {
  provider: string;
  token: string;
  repo_url?: string;
  create_new?: boolean;
}

export interface VercelConnection {
  token: string;
  team_id?: string;
  project_name?: string;
}

export interface AgentGitConfig {
  token?: string;
  repo_name?: string;
  create_new?: boolean;
}

export interface CreateSessionRequest {
  initial_message?: string;
  git?: AgentGitConfig;
}

export interface CreateSessionResponse {
  session_id: string;
  reply?: string;
  message_history?: Array<{ role: string; content: string }>;
}

export interface SendMessageRequest {
  message: string;
  git?: AgentGitConfig;
}

export interface SendMessageResponse {
  reply?: string | null;
  tool_summary?: string[] | null;
  /** When true, client should connect to streamSessionLogs for logs and reply. */
  streaming?: boolean;
}

export interface AgentDeployRequest {
  app_name: string;
  git: GitConnection;
  vercel: VercelConnection;
}

export interface AgentDeployResponse {
  repo_url: string;
  deploy_url?: string | null;
  error?: string | null;
}

@Injectable({ providedIn: 'root' })
export class AgentService {
  private apiBase = DEFAULT_API_BASE;

  constructor(private auth: AuthService) {}

  setApiBase(url: string): void {
    this.apiBase = url.replace(/\/+$/, '');
  }

  getApiBase(): string {
    return this.apiBase;
  }

  private getHeaders(): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    Object.assign(h, this.auth.getAuthHeaders());
    return h;
  }

  async createSession(
    initialMessage?: string,
    git?: AgentGitConfig,
  ): Promise<CreateSessionResponse> {
    const body: CreateSessionRequest = { initial_message: initialMessage ?? undefined };
    if (git?.token) {
      body.git = {
        token: git.token,
        repo_name: git.repo_name,
        create_new: git.create_new ?? true,
      };
    }
    const res = await fetch(`${this.apiBase}/api/agent/sessions`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(body),
    });
    const data = (await res.json().catch(() => ({}))) as CreateSessionResponse & { detail?: string };
    if (!res.ok) {
      throw new Error((data as { detail?: string }).detail || res.statusText || 'Failed to create session');
    }
    return data;
  }

  async sendMessage(
    sessionId: string,
    message: string,
    git?: AgentGitConfig,
  ): Promise<SendMessageResponse> {
    const body: SendMessageRequest = { message };
    if (git?.token) {
      body.git = {
        token: git.token,
        repo_name: git.repo_name,
        create_new: git.create_new ?? true,
      };
    }
    const res = await fetch(`${this.apiBase}/api/agent/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(body),
    });
    const data = (await res.json().catch(() => ({}))) as SendMessageResponse & { detail?: string };
    if (!res.ok) {
      throw new Error((data as { detail?: string }).detail || res.statusText || 'Failed to send message');
    }
    return data;
  }

  async getFiles(sessionId: string, path = '.'): Promise<{ entries: Array<{ name: string; type: string }>; path: string }> {
    const encoded = encodeURIComponent(path);
    const res = await fetch(`${this.apiBase}/api/agent/sessions/${sessionId}/files?path=${encoded}`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to list files');
    }
    return res.json();
  }

  async deploy(sessionId: string, req: AgentDeployRequest): Promise<AgentDeployResponse> {
    const res = await fetch(`${this.apiBase}/api/agent/sessions/${sessionId}/deploy`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(req),
    });
    const data = (await res.json().catch(() => ({}))) as AgentDeployResponse & { detail?: string };
    if (!res.ok) {
      throw new Error((data as { detail?: string }).detail || res.statusText || 'Deploy failed');
    }
    return data;
  }

  async deleteSession(sessionId: string): Promise<void> {
    const res = await fetch(`${this.apiBase}/api/agent/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to delete session');
    }
  }

  /**
   * Stream real-time logs from the agent session via SSE.
   * Connect immediately after createSession returns (when initial_message was provided).
   * Completes on 'done' or error.
   */
  streamSessionLogs(sessionId: string): Observable<AgentLogEvent> {
    return new Observable((subscriber) => {
      const url = `${this.apiBase}/api/agent/sessions/${sessionId}/stream`;
      let cancelled = false;

      (async () => {
        try {
          const res = await fetch(url, { headers: this.getHeaders() });
          if (!res.ok) {
            subscriber.error(new Error(`Stream failed: ${res.statusText}`));
            return;
          }
          const reader = res.body?.getReader();
          if (!reader) {
            subscriber.error(new Error('No response body'));
            return;
          }
          const decoder = new TextDecoder();
          let buffer = '';
          while (!cancelled) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';
            let eventType = '';
            let eventData = '';
            for (const line of lines) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                eventData = line.slice(6);
              } else if (line === '' && eventType && eventData) {
                try {
                  const data = JSON.parse(eventData) as AgentLogEvent;
                  subscriber.next(data);
                  if (data.type === 'done') {
                    subscriber.complete();
                    return;
                  }
                } catch {
                  // ignore parse errors
                }
                eventType = '';
                eventData = '';
              }
            }
          }
          subscriber.complete();
        } catch (err) {
          if (!cancelled) {
            subscriber.error(err);
          }
        }
      })();

      return () => {
        cancelled = true;
      };
    });
  }
}
