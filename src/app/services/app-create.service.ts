import { Injectable } from '@angular/core';

const DEFAULT_API_BASE = 'https://api.kodbro.com';

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

export interface CreateAppRequest {
  app_name: string;
  description: string;
  prompt: string;
  git: GitConnection;
  vercel: VercelConnection;
}

export interface CreateAppResponse {
  job_id?: string;
  message?: string;
  /** Set when server runs create synchronously (e.g. Vercel serverless) */
  repo_url?: string;
  deploy_url?: string;
  error?: string;
}

export type JobStatusType =
  | 'pending'
  | 'generating'
  | 'pushing'
  | 'deploying'
  | 'done'
  | 'failed';

export interface AppStatusResponse {
  job_id: string;
  status: JobStatusType;
  message?: string;
  repo_url?: string;
  deploy_url?: string;
  error?: string;
  details?: Record<string, unknown>;
}

@Injectable({ providedIn: 'root' })
export class AppCreateService {
  private apiBase = DEFAULT_API_BASE;

  setApiBase(url: string): void {
    this.apiBase = url.replace(/\/+$/, '');
  }

  getApiBase(): string {
    return this.apiBase;
  }

  async createApp(req: CreateAppRequest): Promise<CreateAppResponse> {
    const res = await fetch(`${this.apiBase}/api/apps/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    const data = (await res.json().catch(() => ({}))) as CreateAppResponse & { detail?: string };
    if (!res.ok) {
      throw new Error(data.error || data.detail || res.statusText || 'Create failed');
    }
    return data;
  }

  async getStatus(jobId: string): Promise<AppStatusResponse> {
    const res = await fetch(`${this.apiBase}/api/apps/status/${jobId}`);
    if (!res.ok) {
      if (res.status === 404) throw new Error('Job not found');
      throw new Error('Status check failed');
    }
    return res.json() as Promise<AppStatusResponse>;
  }
}
