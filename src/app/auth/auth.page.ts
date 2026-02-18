import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-auth',
  templateUrl: './auth.page.html',
  styleUrls: ['./auth.page.scss'],
  standalone: false,
})
export class AuthPage implements OnInit {

  constructor(private router: Router) { }

  ngOnInit() {
  }

  signIn() {
    this.router.navigate(['/home']);
  }

}
