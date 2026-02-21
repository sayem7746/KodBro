import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-auth',
  templateUrl: './auth.page.html',
  styleUrls: ['./auth.page.scss'],
  standalone: false,
})
export class AuthPage implements OnInit {
  email = '';
  password = '';
  displayName = '';
  isSignUp = false;
  loading = false;
  error: string | null = null;

  constructor(
    private router: Router,
    private auth: AuthService,
  ) {}

  ngOnInit(): void {
    if (this.auth.isAuthenticated()) {
      this.router.navigate(['/home']);
    }
  }

  toggleMode(): void {
    this.isSignUp = !this.isSignUp;
    this.error = null;
  }

  async onSubmit(): Promise<void> {
    this.error = null;
    const email = this.email.trim();
    const password = this.password.trim();
    if (!email || !password) {
      this.error = 'Email and password are required';
      return;
    }
    if (this.isSignUp && password.length < 8) {
      this.error = 'Password must be at least 8 characters';
      return;
    }
    this.loading = true;
    try {
      if (this.isSignUp) {
        await this.auth.signup(email, password, this.displayName.trim() || undefined);
      } else {
        await this.auth.login(email, password);
      }
      this.router.navigate(['/home']);
    } catch (err) {
      this.error = err instanceof Error ? err.message : 'Something went wrong';
    } finally {
      this.loading = false;
    }
  }
}
