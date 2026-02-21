import { AfterViewChecked, Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  AgentService,
  CreateSessionResponse,
  AgentDeployRequest,
  AgentDeployResponse,
  AgentGitConfig,
} from '../services/agent.service';
import { AuthService } from '../services/auth.service';

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
export class AgentPage implements OnInit, OnDestroy, AfterViewChecked {
  // Session state
  sessionId: string | null = null;
  messages: ChatMessage[] = [];
  loading = false;
  error: string | null = null;

  // Real-time build logs (streamed from backend)
  logs: string[] = [];
  showLogPanel = true;
  streamSubscription: Subscription | null = null;

  @ViewChild('logContainer') logContainer?: ElementRef<HTMLDivElement>;
  private logsLengthPrev = 0;

  // Start form (before session exists)
  initialPrompt = '';
  starting = false;

  // App title for repo name
  agentAppTitle = 'my-app';
  agentRepoId = '';
  agentGitCreateNew = true;

  tokensLoaded = false;

  // Chat input
  chatInput = '';

  // Deploy
  showDeployForm = false;
  deployAppName = 'my-app';
  deployRepoId = '';
  gitToken = '';
  gitCreateNew = true;
  gitRepoUrl = '';
  vercelToken = '';
  vercelTeamId = '';
  deployResult: AgentDeployResponse | null = null;
  deploying = false;

  gitTokenStored = false;
  vercelTokenStored = false;

  private storedAgentGitToken: string | null = null;
  private storedDeployGitToken: string | null = null;
  private storedDeployVercelToken: string | null = null;

  constructor(
    private agent: AgentService,
    private router: Router,
    private route: ActivatedRoute,
    private auth: AuthService,
  ) {}

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
          this.storedAgentGitToken = d.value;
          this.storedDeployGitToken = d.value;
          this.gitTokenStored = true;
        }
      }
      if (vercelRes.ok) {
        const d = (await vercelRes.json()) as { value?: string };
        if (d.value) {
          this.storedDeployVercelToken = d.value;
          this.vercelTokenStored = true;
        }
      }
    } catch {
      // ignore
    } finally {
      this.tokensLoaded = true;
    }
  }

  private get effectiveAgentGitToken(): string {
    return this.storedAgentGitToken || '';
  }

  private get effectiveDeployGitToken(): string {
    const t = this.gitToken?.trim();
    return t || this.storedDeployGitToken || '';
  }

  private get effectiveDeployVercelToken(): string {
    const t = this.vercelToken?.trim();
    return t || this.storedDeployVercelToken || '';
  }

  async ngOnInit(): Promise<void> {
    const defaults = environment.agentDefaults;
    this.initialPrompt = defaults?.initialPrompt ?? '';
    this.agentAppTitle = defaults?.repoNamePrefix ?? 'my-app';
    this.agentRepoId = this.randomHash();
    this.deployRepoId = this.randomHash();

    await this.loadStoredTokens();

    const prompt = this.route.snapshot.queryParamMap.get('prompt');
    if (prompt?.trim() && this.gitTokenStored) {
      this.initialPrompt = prompt.trim();
      void this.startSession();
    }
  }

  private randomHash(): string {
    return Math.random().toString(36).substring(2, 10);
  }

  normalizeAppTitle(value: string): string {
    return value.replace(/\s/g, '').toLowerCase();
  }

  ngOnDestroy(): void {
    this.streamSubscription?.unsubscribe();
  }

  ngAfterViewChecked(): void {
    if (this.logs.length !== this.logsLengthPrev && this.logContainer?.nativeElement) {
      this.logsLengthPrev = this.logs.length;
      this.logContainer.nativeElement.scrollTop = this.logContainer.nativeElement.scrollHeight;
    }
  }

  getLogType(log: string): string {
    if (log.startsWith('[Thinking]')) return 'thinking';
    if (log.startsWith('[Tool]')) return 'tool';
    if (log.startsWith('[Result]')) return 'result';
    if (log.startsWith('[Round]')) return 'round';
    if (log.startsWith('[Step]')) return 'step';
    if (log.startsWith('[Agent]') || log.startsWith('[Cursor]')) return 'agent';
    if (log.startsWith('[Progress]')) return 'progress';
    if (log.startsWith('[Activity]')) return 'activity';
    if (log.startsWith('[Status]')) return 'status';
    if (log.startsWith('[Polling]')) return 'polling';
    return 'info';
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
      const repoName = this.agentGitCreateNew
        ? `${(this.agentAppTitle || 'my-app').trim()}-${this.agentRepoId}`
        : undefined;
      const git: AgentGitConfig | undefined =
        this.effectiveAgentGitToken
          ? {
              token: this.effectiveAgentGitToken,
              repo_name: repoName,
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
    this.logs = [];

    try {
      const repoName = this.agentGitCreateNew
        ? `${(this.agentAppTitle || 'my-app').trim()}-${this.agentRepoId}`
        : undefined;
      const git: AgentGitConfig | undefined =
        this.effectiveAgentGitToken
          ? {
              token: this.effectiveAgentGitToken,
              repo_name: repoName,
              create_new: this.agentGitCreateNew,
            }
          : undefined;
      const res = await this.agent.sendMessage(this.sessionId, msg, git);

      if (res.streaming) {
        this.streamSubscription?.unsubscribe();
        this.streamSubscription = this.agent.streamSessionLogs(this.sessionId).subscribe({
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
      } else {
        this.messages.push({
          role: 'assistant',
          content: res.reply ?? '',
          toolSummary: res.tool_summary ?? undefined,
        });
        this.loading = false;
      }
    } catch (e) {
      this.error = e instanceof Error ? e.message : 'Failed to send message';
      this.messages.pop(); // Remove the user message we added
      this.loading = false;
    }
  }

  openDeployForm(): void {
    this.showDeployForm = true;
    this.deployResult = null;
    this.deployRepoId = this.randomHash();
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
    if (!this.effectiveDeployGitToken) {
      this.error = 'Git token is required (enter one or save in Settings)';
      return;
    }
    if (!this.effectiveDeployVercelToken) {
      this.error = 'Vercel token is required (enter one or save in Settings)';
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
      const baseName = this.deployAppName.trim() || 'my-app';
      const appNameForRepo = this.gitCreateNew
        ? `${baseName}-${this.deployRepoId}`
        : baseName;
      const req: AgentDeployRequest = {
        app_name: appNameForRepo,
        git: {
          provider: 'github',
          token: this.effectiveDeployGitToken,
          create_new: this.gitCreateNew,
          repo_url: this.gitRepoUrl?.trim() || undefined,
        },
        vercel: {
          token: this.effectiveDeployVercelToken,
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
