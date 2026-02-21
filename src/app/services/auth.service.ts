import { Injectable } from '@angular/core';

const TOKEN_KEY = 'kodbro_access_token';
const USER_KEY = 'kodbro_user';

export interface AuthUser {
  user_id: string;
  email: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private apiBase = 'https://agent.kodbro.com';

  setApiBase(url: string): void {
    this.apiBase = url.replace(/\/+$/, '');
  }

  getApiBase(): string {
    return this.apiBase;
  }

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  private setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  }

  private setUser(user: AuthUser): void {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  getUser(): AuthUser | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      return null;
    }
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  getAuthHeaders(): Record<string, string> {
    const token = this.getToken();
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  }

  /**
   * Fetch with auth headers. Use for API calls that require authentication.
   */
  async fetchWithAuth(url: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    const auth = this.getAuthHeaders();
    for (const [k, v] of Object.entries(auth)) {
      headers.set(k, v);
    }
    if (!headers.has('Content-Type') && init.body && typeof init.body === 'string') {
      headers.set('Content-Type', 'application/json');
    }
    return fetch(url, { ...init, headers });
  }

  async signup(
    email: string,
    password: string,
    displayName?: string
  ): Promise<AuthResponse> {
    const res = await fetch(`${this.apiBase}/api/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        password,
        display_name: displayName || null,
      }),
    });
    const data = (await res.json().catch(() => ({}))) as AuthResponse & { detail?: string };
    if (!res.ok) {
      throw new Error(data.detail || res.statusText || 'Signup failed');
    }
    this.setToken(data.access_token);
    this.setUser({ user_id: data.user_id, email: data.email });
    return data;
  }

  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await fetch(`${this.apiBase}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = (await res.json().catch(() => ({}))) as AuthResponse & { detail?: string };
    if (!res.ok) {
      throw new Error(data.detail || res.statusText || 'Login failed');
    }
    this.setToken(data.access_token);
    this.setUser({ user_id: data.user_id, email: data.email });
    return data;
  }
}
