import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.page.html',
  styleUrls: ['./settings.page.scss'],
  standalone: false,
})
export class SettingsPage implements OnInit {
  githubToken = '';
  vercelToken = '';
  vercelTeamId = '';
  railwayToken = '';

  githubStored = false;
  vercelStored = false;
  railwayStored = false;

  saving = false;
  message: string | null = null;
  error: string | null = null;

  constructor(
    private auth: AuthService,
    private router: Router,
  ) {}

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/auth']);
  }

  ngOnInit(): void {
    this.loadStoredStatus();
  }

  private get apiBase(): string {
    return this.auth.getApiBase();
  }

  private get headers(): Record<string, string> {
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    Object.assign(h, this.auth.getAuthHeaders());
    return h;
  }

  async loadStoredStatus(): Promise<void> {
    try {
      const res = await fetch(`${this.apiBase}/api/user/tokens`, {
        headers: this.headers,
      });
      if (!res.ok) return;
      const list = (await res.json()) as Array<{ provider: string }>;
      this.githubStored = list.some((t) => t.provider === 'github');
      this.vercelStored = list.some((t) => t.provider === 'vercel');
      this.railwayStored = list.some((t) => t.provider === 'railway');
    } catch {
      // ignore
    }
  }

  async saveGithub(): Promise<void> {
    if (!this.githubToken.trim()) {
      this.error = 'Token is required';
      return;
    }
    await this.saveToken('github', this.githubToken);
    if (!this.error) {
      this.githubToken = '';
      this.githubStored = true;
    }
  }

  async saveVercel(): Promise<void> {
    if (!this.vercelToken.trim()) {
      this.error = 'Token is required';
      return;
    }
    await this.saveToken('vercel', this.vercelToken, this.vercelTeamId.trim() || undefined);
    if (!this.error) {
      this.vercelToken = '';
      this.vercelTeamId = '';
      this.vercelStored = true;
    }
  }

  async saveRailway(): Promise<void> {
    if (!this.railwayToken.trim()) {
      this.error = 'Token is required';
      return;
    }
    await this.saveToken('railway', this.railwayToken);
    if (!this.error) {
      this.railwayToken = '';
      this.railwayStored = true;
    }
  }

  private async saveToken(
    provider: string,
    value: string,
    teamId?: string
  ): Promise<void> {
    this.error = null;
    this.message = null;
    this.saving = true;
    try {
      const body: { value: string; team_id?: string } = { value };
      if (teamId) body.team_id = teamId;
      const res = await fetch(`${this.apiBase}/api/user/tokens/${provider}`, {
        method: 'PUT',
        headers: this.headers,
        body: JSON.stringify(body),
      });
      const data = (await res.json().catch(() => ({}))) as { detail?: string };
      if (!res.ok) {
        this.error = data.detail || res.statusText || 'Failed to save';
        return;
      }
      this.message = `${provider} token saved`;
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Failed to save';
    } finally {
      this.saving = false;
    }
  }
}
