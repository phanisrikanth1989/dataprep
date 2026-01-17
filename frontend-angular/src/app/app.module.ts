import { NgModule, LOCALE_ID } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientModule } from '@angular/common/http';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { NZ_I18N, en_US } from 'ng-zorro-antd/i18n';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { SharedModule } from './shared/shared.module';
import { LoginComponent } from './pages/login.component';
import { JobListComponent } from './pages/job-list.component';
import { JobDesignerComponent } from './pages/job-designer.component';

// Services
import { ApiService } from './core/services/api.service';
import { AuthService } from './core/services/auth.service';
import { JobService } from './core/services/job.service';
import { ExecutionService } from './core/services/execution.service';
import { WebSocketService } from './core/services/websocket.service';
import { ComponentRegistryService } from './core/services/component-registry.service';

// Guards
import { AuthGuard } from './core/guards/auth.guard';

// Ant Design Modules
import { NzLayoutModule } from 'ng-zorro-antd/layout';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzMessageModule } from 'ng-zorro-antd/message';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzPopconfirmModule } from 'ng-zorro-antd/popconfirm';

@NgModule({
  declarations: [AppComponent, LoginComponent, JobListComponent, JobDesignerComponent],
  imports: [
    BrowserModule,
    AppRoutingModule,
    BrowserAnimationsModule,
    HttpClientModule,
    ReactiveFormsModule,
    FormsModule,
    SharedModule,
    NzLayoutModule,
    NzButtonModule,
    NzMessageModule,
    NzModalModule,
    NzGridModule,
    NzFormModule,
    NzInputModule,
    NzPopconfirmModule,
  ],
  providers: [
    { provide: NZ_I18N, useValue: en_US },
    { provide: LOCALE_ID, useValue: 'en' },
    ApiService,
    AuthService,
    JobService,
    ExecutionService,
    WebSocketService,
    ComponentRegistryService,
    AuthGuard,
  ],
  bootstrap: [AppComponent],
})
export class AppModule {}
