import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { IonicModule } from '@ionic/angular';
import { RouterModule } from '@angular/router';

import { CreateAppPageRoutingModule } from './create-app-routing.module';
import { CreateAppPage } from './create-app.page';

@NgModule({
  imports: [
    CommonModule,
    FormsModule,
    IonicModule,
    RouterModule,
    CreateAppPageRoutingModule,
  ],
  declarations: [CreateAppPage],
})
export class CreateAppPageModule {}
