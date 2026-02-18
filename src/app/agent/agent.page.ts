import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import {
  AgentService,
  CreateSessionResponse,
  AgentDeployRequest,
  AgentDeployResponse,
} from '../services/agent.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolSummary?: string[];
}

@Component({
  selector: 'app-agent',
  templateUrl: './agent.page.html',
  styleUrls: ['./agent.page.scss'],
  standalone: false,
})
export class AgentPage implements OnInit {
  // Session state
  sessionId: string | null = null;
  messages: ChatMessage[] = [];
  loading = false;
  error: string | null = null;

  // Start form (before session exists)
  initialPrompt = '';
  starting = false;

  // Chat input
  chatInput = '';

  // Deploy
  showDeployForm = false;
  deployAppName = 'my-app';
  gitToken = '';
  gitCreateNew = true;
  gitRepoUrl = '';
  vercelToken = '';
  vercelTeamId = '';
  deployResult: AgentDeployResponse | null = null;
  deploying = false;

  constructor(
    private agent: AgentService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    // Session is created on first user action (start or send)
  }

  async startSession(): Promise<void> {
    this.error = null;
    const msg = this.initialPrompt?.trim();
    if (!msg) {
      this.error = 'Describe what you want to build';
      return;
    }
    this.starting = true;
    try {
      const res: CreateSessionResponse = await this.agent.createSession(msg);
      this.sessionId = res.session_id;
      this.messages.push({ role: 'user', content: msg });
      if (res.reply) {
        this.messages.push({ role: 'assistant', content: res.reply });
      }
      this.initialPrompt = '';
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'Failed to start';
    } finally {
      this.starting = false;
    }
  }

  async sendMessage(): Promise<void> {
    const msg = this.chatInput?.trim();
    if (!msg || !this.sessionId) return;

    this.error = null;
    this.messages.push({ role: 'user', content: msg });
    this.chatInput = '';
    this.loading = true;

    try {
      const res = await this.agent.sendMessage(this.sessionId, msg);
      this.messages.push({
        role: 'assistant',
        content: res.reply,
        toolSummary: res.tool_summary,
      });
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'Failed to send message';
      this.messages.pop(); // Remove the user message we added
    } finally {
      this.loading = false;
    }
  }

  openDeployForm(): void {
    this.showDeployForm = true;
    this.deployResult = null;
  }

  closeDeployForm(): void {
    this.showDeployForm = false;
    this.deployResult = null;
  }

  async deploy(): Promise<void> {
    this.error = null;
    if (!this.deployAppName?.trim()) {
      this.error = 'App name is required';
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
      this.error = 'Repo URL is required when not creating a new repo';
      return;
    }
    if (!this.sessionId) return;

    this.deploying = true;
    this.deployResult = null;
    try {
      const req: AgentDeployRequest = {
        app_name: this.deployAppName.trim(),
        git: {
          provider: 'github',
          token: this.gitToken.trim(),
          create_new: this.gitCreateNew,
          repo_url: this.gitRepoUrl?.trim() || undefined,
        },
        vercel: {
          token: this.vercelToken.trim(),
          team_id: this.vercelTeamId?.trim() || undefined,
        },
      };
      this.deployResult = await this.agent.deploy(this.sessionId, req);
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'Deploy failed';
    } finally {
      this.deploying = false;
    }
  }

  goHome(): void {
    this.router.navigate(['/home']);
  }

  get deploySuccess(): boolean {
    return !!this.deployResult?.repo_url && !this.deployResult?.error;
  }
}
