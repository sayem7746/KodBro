import { Component } from '@angular/core';
import { Router } from '@angular/router';

const MAIN_ROUTES = ['/home', '/agent', '/create-app', '/history', '/settings'];

@Component({
  selector: 'app-root',
  templateUrl: 'app.component.html',
  styleUrls: ['app.component.scss'],
  standalone: false,
})
export class AppComponent {
  constructor(private router: Router) {}

  get showBottomNav(): boolean {
    const url = this.router.url.split('?')[0];
    return MAIN_ROUTES.some((r) => url === r || url.startsWith(r + '/'));
  }
}
