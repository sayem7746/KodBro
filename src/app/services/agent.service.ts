import { Injectable } from '@angular/core';

const DEFAULT_API_BASE = 'https://agent.kodbro.com';

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
  reply: string;
  tool_summary?: string[];
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

  setApiBase(url: string): void {
    this.apiBase = url.replace(/\/+$/, '');
  }

  getApiBase(): string {
    return this.apiBase;
  }

  async createSession(
    initialMessage?: string,
    git?: AgentGitConfig,
  ): Promise<CreateSessionResponse> {
    const body: CreateSessionRequest = { initial_message: initialMessage || null };
    if (git?.token) {
      body.git = {
        token: git.token,
        repo_name: git.repo_name,
        create_new: git.create_new ?? true,
      };
    }
    const res = await fetch(`${this.apiBase}/api/agent/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
      headers: { 'Content-Type': 'application/json' },
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
    const res = await fetch(`${this.apiBase}/api/agent/sessions/${sessionId}/files?path=${encoded}`);
    if (!res.ok) {
      throw new Error('Failed to list files');
    }
    return res.json();
  }

  async deploy(sessionId: string, req: AgentDeployRequest): Promise<AgentDeployResponse> {
    const res = await fetch(`${this.apiBase}/api/agent/sessions/${sessionId}/deploy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
    });
    if (!res.ok) {
      throw new Error('Failed to delete session');
    }
  }
}
