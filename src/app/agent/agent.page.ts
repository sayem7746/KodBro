import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription } from 'rxjs';
import {
  AgentService,
  CreateSessionResponse,
  AgentDeployRequest,
  AgentDeployResponse,
  AgentGitConfig,
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
export class AgentPage implements OnInit, OnDestroy {
  // Session state
  sessionId: string | null = null;
  messages: ChatMessage[] = [];
  loading = false;
  error: string | null = null;

  // Real-time build logs (streamed from backend)
  logs: string[] = [];
  showLogPanel = true;
  streamSubscription: Subscription | null = null;

  // Start form (before session exists)
  initialPrompt = '';
  starting = false;

  // GitHub connection (optional, for Cursor agent - create repos in user's account)
  showGitConnect = false;
  agentGitToken = '';
  agentRepoName = 'my-app';
  agentGitCreateNew = true;

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
    private route: ActivatedRoute,
  ) {}

  ngOnInit(): void {
    const prompt = this.route.snapshot.queryParamMap.get('prompt');
    if (prompt?.trim()) {
      this.initialPrompt = prompt.trim();
      void this.startSession();
    }
  }

  ngOnDestroy(): void {
    this.streamSubscription?.unsubscribe();
  }

  async startSession(): Promise<void> {
    this.error = null;
    const msg = this.initialPrompt?.trim();
    if (!msg) {
      this.error = 'Describe what you want to build';
      return;
    }
    this.starting = true;
    this.logs = [];
    try {
      const git: AgentGitConfig | undefined =
        this.agentGitToken?.trim()
          ? {
              token: this.agentGitToken.trim(),
              repo_name: this.agentRepoName?.trim() || undefined,
              create_new: this.agentGitCreateNew,
            }
          : undefined;
      const res: CreateSessionResponse = await this.agent.createSession(msg, git);
      this.sessionId = res.session_id;
      this.messages.push({ role: 'user', content: msg });
      this.initialPrompt = '';

      if (res.reply) {
        this.messages.push({ role: 'assistant', content: res.reply });
      } else {
        this.loading = true;
        this.streamSubscription = this.agent.streamSessionLogs(res.session_id).subscribe({
          next: (ev) => {
            if (ev.type === 'log') {
              this.logs = [...this.logs, ev.message];
            } else if (ev.type === 'done') {
              this.messages.push({
                role: 'assistant',
                content: ev.reply,
                toolSummary: ev.tool_summary,
              });
              this.loading = false;
              this.streamSubscription?.unsubscribe();
              this.streamSubscription = null;
            } else if (ev.type === 'error') {
              this.error = ev.error;
            }
          },
          error: (err) => {
            this.error = err instanceof Error ? err.message : 'Stream failed';
            this.loading = false;
            this.streamSubscription = null;
          },
        });
      }
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
      const git: AgentGitConfig | undefined =
        this.agentGitToken?.trim()
          ? {
              token: this.agentGitToken.trim(),
              repo_name: this.agentRepoName?.trim() || undefined,
              create_new: this.agentGitCreateNew,
            }
          : undefined;
      const res = await this.agent.sendMessage(this.sessionId, msg, git);
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
