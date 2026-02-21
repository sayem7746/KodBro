import { Component, ViewChild, ElementRef, AfterViewChecked, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { TerminalService } from '../services/terminal.service';

@Component({
  selector: 'app-home',
  templateUrl: 'home.page.html',
  styleUrls: ['home.page.scss'],
  standalone: false,
})
export class HomePage implements OnInit, AfterViewChecked {
  @ViewChild('outputEl') outputEl!: ElementRef<HTMLDivElement>;

  commandInput = '';
  serverUrl = 'https://agent.kodbro.com';
  private shouldScroll = false;

  constructor(
    public terminal: TerminalService,
    private router: Router,
    private auth: AuthService,
  ) {}

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/auth']);
  }

  ngOnInit(): void {
    if (!this.terminal.connection.connected) {
      this.terminal.serverUrl = this.serverUrl;
      this.terminal.connect();
    }
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll && this.outputEl?.nativeElement) {
      this.outputEl.nativeElement.scrollTop = this.outputEl.nativeElement.scrollHeight;
      this.shouldScroll = false;
    }
  }

  onCommandKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.runCommand();
    }
  }

  runCommand(): void {
    const cmd = this.commandInput.trim();
    if (!cmd) return;
    if (cmd.toLowerCase() === 'create') {
      this.commandInput = '';
      this.router.navigate(['/create-app']);
      return;
    }
    // Natural language like "create a movie" or "create an app" → route to Agent
    const lower = cmd.toLowerCase();
    if (lower.startsWith('create ') && lower.length > 7) {
      this.commandInput = '';
      this.router.navigate(['/agent'], { queryParams: { prompt: cmd } });
      return;
    }
    this.terminal.executeCommand(cmd);
    this.commandInput = '';
    this.shouldScroll = true;
  }

  setHistoryPrev(): void {
    const prev = this.terminal.getHistory('prev');
    if (prev !== null) this.commandInput = prev;
  }

  setHistoryNext(): void {
    const next = this.terminal.getHistory('next');
    if (next !== null) this.commandInput = next;
  }

  connect(): void {
    this.terminal.serverUrl = this.serverUrl;
    this.terminal.connect();
    this.shouldScroll = true;
  }

  disconnect(): void {
    this.terminal.disconnect();
    this.shouldScroll = true;
  }
}
