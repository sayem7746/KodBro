import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-splash',
  templateUrl: './splash.page.html',
  styleUrls: ['./splash.page.scss'],
  standalone: false,
})
export class SplashPage implements OnInit {
  constructor(
    private router: Router,
    private auth: AuthService,
  ) {}

  ngOnInit() {
    setTimeout(() => {
      this.router.navigate([this.auth.isAuthenticated() ? '/home' : '/welcome']);
    }, 2500);
  }
}
