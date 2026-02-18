import { Component, OnDestroy } from '@angular/core';
import { Router } from '@angular/router';
import {
  AppCreateService,
  CreateAppRequest,
  AppStatusResponse,
} from '../services/app-create.service';

@Component({
  selector: 'app-create-app',
  templateUrl: './create-app.page.html',
  styleUrls: ['./create-app.page.scss'],
  standalone: false,
})
export class CreateAppPage implements OnDestroy {
  appName = '';
  description = '';
  prompt = '';
  gitToken = '';
  gitCreateNew = true;
  gitRepoUrl = '';
  vercelToken = '';
  vercelTeamId = '';
  vercelProjectName = '';

  submitting = false;
  error: string | null = null;
  jobId: string | null = null;
  status: AppStatusResponse | null = null;
  pollInterval: ReturnType<typeof setInterval> | null = null;

  constructor(
    private appCreate: AppCreateService,
    private router: Router
  ) {}

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
    if (!this.gitToken?.trim()) {
      this.error = 'Git token is required';
      return;
    }
    if (!this.vercelToken?.trim()) {
      this.error = 'Vercel token is required';
      return;
    }
    if (!this.gitCreateNew && !this.gitRepoUrl?.trim()) {
      this.error = 'Git repo URL is required when not creating a new repo';
      return;
    }

    this.submitting = true;
    try {
      const req: CreateAppRequest = {
        app_name: this.appName.trim(),
        description: this.description.trim(),
        prompt: this.prompt.trim(),
        git: {
          provider: 'github',
          token: this.gitToken.trim(),
          create_new: this.gitCreateNew,
          repo_url: this.gitRepoUrl?.trim() || undefined,
        },
        vercel: {
          token: this.vercelToken.trim(),
          team_id: this.vercelTeamId?.trim() || undefined,
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
  }
}
