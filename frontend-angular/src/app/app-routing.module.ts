import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { LoginComponent } from './pages/login.component';
import { JobListComponent } from './pages/job-list.component';
import { JobDesignerComponent } from './pages/job-designer.component';
import { ExecutionMonitorComponent } from './shared/components/execution-monitor.component';
import { AuthGuard } from './core/guards/auth.guard';

const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: '', component: JobListComponent, canActivate: [AuthGuard] },
  { path: 'designer/:jobId', component: JobDesignerComponent, canActivate: [AuthGuard] },
  { path: 'execution/:taskId', component: ExecutionMonitorComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
})
export class AppRoutingModule {}
