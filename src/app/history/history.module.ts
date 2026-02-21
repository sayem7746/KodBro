import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { IonicModule } from '@ionic/angular';
import { RouterModule } from '@angular/router';

import { HistoryPageRoutingModule } from './history-routing.module';
import { HistoryPage } from './history.page';

@NgModule({
  imports: [
    CommonModule,
    IonicModule,
    RouterModule,
    HistoryPageRoutingModule,
  ],
  declarations: [HistoryPage],
})
export class HistoryPageModule {}
