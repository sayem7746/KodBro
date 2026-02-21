import { Component, OnDestroy, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import {
  AppCreateService,
  CreateAppRequest,
  AppStatusResponse,
} from '../services/app-create.service';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-create-app',
  templateUrl: './create-app.page.html',
  styleUrls: ['./create-app.page.scss'],
  standalone: false,
})
export class CreateAppPage implements OnInit, OnDestroy {
  appName = '';
  description = '';
  prompt = '';
  gitToken = '';
  gitCreateNew = true;
  gitRepoUrl = '';
  vercelToken = '';
  vercelTeamId = '';
  vercelProjectName = '';

  gitTokenStored = false;
  vercelTokenStored = false;

  repoId = '';

  submitting = false;
  error: string | null = null;
  jobId: string | null = null;
  status: AppStatusResponse | null = null;
  pollInterval: ReturnType<typeof setInterval> | null = null;

  private storedGitToken: string | null = null;
  private storedVercelToken: string | null = null;
  private storedVercelTeamId: string | null = null;

  constructor(
    private appCreate: AppCreateService,
    private router: Router,
    private auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.repoId = this.randomHash();
    void this.loadStoredTokens();
  }

  private randomHash(): string {
    return Math.random().toString(36).substring(2, 10);
  }

  normalizeAppName(value: string): string {
    return value.replace(/\s/g, '').toLowerCase();
  }

  private async loadStoredTokens(): Promise<void> {
    const base = this.auth.getApiBase();
    const headers = this.auth.getAuthHeaders();
    try {
      const [gitRes, vercelRes] = await Promise.all([
        fetch(`${base}/api/user/tokens/github`, { headers }),
        fetch(`${base}/api/user/tokens/vercel`, { headers }),
      ]);
      if (gitRes.ok) {
        const d = (await gitRes.json()) as { value?: string };
        if (d.value) {
          this.storedGitToken = d.value;
          this.gitTokenStored = true;
        }
      }
      if (vercelRes.ok) {
        const d = (await vercelRes.json()) as { value?: string };
        if (d.value) {
          this.storedVercelToken = d.value;
          this.vercelTokenStored = true;
        }
      }
    } catch {
      // ignore
    }
  }

  private get effectiveGitToken(): string {
    const t = this.gitToken?.trim();
    return t || this.storedGitToken || '';
  }

  private get effectiveVercelToken(): string {
    const t = this.vercelToken?.trim();
    return t || this.storedVercelToken || '';
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  private stopPolling(): void {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  async submit(): Promise<void> {
    this.error = null;
    if (!this.appName?.trim()) {
      this.error = 'App name is required';
      return;
    }
    if (!this.prompt?.trim()) {
      this.error = 'Prompt is required';
      return;
    }
    if (!this.effectiveGitToken) {
      this.error = 'Git token is required (enter one or save in Settings)';
      return;
    }
    if (!this.effectiveVercelToken) {
      this.error = 'Vercel token is required (enter one or save in Settings)';
      return;
    }
    if (!this.gitCreateNew && !this.gitRepoUrl?.trim()) {
      this.error = 'Git repo URL is required when not creating a new repo';
      return;
    }

    this.submitting = true;
    try {
      const baseName = this.appName.trim() || 'my-app';
      const appNameForRepo = this.gitCreateNew
        ? `${baseName}-${this.repoId}`
        : baseName;
      const req: CreateAppRequest = {
        app_name: appNameForRepo,
        description: this.description.trim(),
        prompt: this.prompt.trim(),
        git: {
          provider: 'github',
          token: this.effectiveGitToken,
          create_new: this.gitCreateNew,
          repo_url: this.gitRepoUrl?.trim() || undefined,
        },
        vercel: {
          token: this.effectiveVercelToken,
          team_id: this.vercelTeamId?.trim() || this.storedVercelTeamId || undefined,
          project_name: this.vercelProjectName?.trim() || undefined,
        },
      };
      const res = await this.appCreate.createApp(req);
      if (res.repo_url || res.deploy_url) {
        this.status = {
          job_id: '',
          status: 'done',
          message: res.message ?? 'App created',
          repo_url: res.repo_url,
          deploy_url: res.deploy_url,
        };
        this.jobId = null;
      } else if (res.job_id) {
        this.jobId = res.job_id;
        this.startPolling();
      } else {
        this.error = res.error ?? 'Unexpected response from server';
      }
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'Failed to start creation';
    } finally {
      this.submitting = false;
    }
  }

  private startPolling(): void {
    this.stopPolling();
    const check = async () => {
      if (!this.jobId) return;
      try {
        this.status = await this.appCreate.getStatus(this.jobId);
        if (this.status.status === 'done' || this.status.status === 'failed') {
          this.stopPolling();
        }
      } catch {
        this.stopPolling();
      }
    };
    check();
    this.pollInterval = setInterval(check, 2500);
  }

  get isFinished(): boolean {
    const s = this.status?.status;
    return s === 'done' || s === 'failed';
  }

  get isSuccess(): boolean {
    return this.status?.status === 'done';
  }

  goHome(): void {
    this.stopPolling();
    this.router.navigate(['/home']);
  }

  reset(): void {
    this.stopPolling();
    this.jobId = null;
    this.status = null;
    this.error = null;
    this.repoId = this.randomHash();
  }
}
