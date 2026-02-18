import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { CreateAppPage } from './create-app.page';

const routes: Routes = [
  {
    path: '',
    component: CreateAppPage,
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class CreateAppPageRoutingModule {}
