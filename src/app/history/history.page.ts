import { Component, OnInit } from '@angular/core';
import { AuthService } from '../services/auth.service';

interface JobItem {
  id: string;
  app_name: string;
  status: string;
  repo_url: string | null;
  deploy_url: string | null;
  created_at: string | null;
}

@Component({
  selector: 'app-history',
  templateUrl: './history.page.html',
  styleUrls: ['./history.page.scss'],
  standalone: false,
})
export class HistoryPage implements OnInit {
  jobs: JobItem[] = [];
  loading = true;
  error: string | null = null;

  constructor(private auth: AuthService) {}

  ngOnInit(): void {
    void this.loadJobs();
  }

  private get headers(): Record<string, string> {
    const h: Record<string, string> = {};
    Object.assign(h, this.auth.getAuthHeaders());
    return h;
  }

  async loadJobs(): Promise<void> {
    this.loading = true;
    this.error = null;
    try {
      const res = await fetch(`${this.auth.getApiBase()}/api/user/jobs`, {
        headers: this.headers,
      });
      if (!res.ok) {
        throw new Error(res.statusText || 'Failed to load');
      }
      this.jobs = (await res.json()) as JobItem[];
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to load jobs';
      this.jobs = [];
    } finally {
      this.loading = false;
    }
  }

  formatDate(iso: string | null): string {
    if (!iso) return '-';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  }

  statusColor(status: string): string {
    switch (status) {
      case 'done':
        return 'success';
      case 'failed':
        return 'danger';
      case 'pending':
      case 'generating':
      case 'pushing':
      case 'deploying':
        return 'warning';
      default:
        return 'medium';
    }
  }
}
