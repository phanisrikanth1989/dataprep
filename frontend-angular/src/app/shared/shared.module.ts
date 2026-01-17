import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { NzModalModule } from 'ng-zorro-antd/modal';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzCheckboxModule } from 'ng-zorro-antd/checkbox';
import { NzProgressModule } from 'ng-zorro-antd/progress';
import { NzPopconfirmModule } from 'ng-zorro-antd/popconfirm';
import { NzMessageModule } from 'ng-zorro-antd/message';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzGridModule } from 'ng-zorro-antd/grid';
import { NzLayoutModule } from 'ng-zorro-antd/layout';

import { CanvasComponent } from './components/canvas.component';
import { ComponentPaletteComponent } from './components/component-palette.component';
import { ConfigPanelComponent } from './components/config-panel.component';
import { ExecutionMonitorComponent } from './components/execution-monitor.component';

@NgModule({
  declarations: [
    CanvasComponent,
    ComponentPaletteComponent,
    ConfigPanelComponent,
    ExecutionMonitorComponent,
  ],
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    HttpClientModule,
    NzModalModule,
    NzButtonModule,
    NzInputModule,
    NzSelectModule,
    NzCheckboxModule,
    NzProgressModule,
    NzPopconfirmModule,
    NzMessageModule,
    NzSpinModule,
    NzGridModule,
    NzLayoutModule,
  ],
  exports: [
    CanvasComponent,
    ComponentPaletteComponent,
    ConfigPanelComponent,
    ExecutionMonitorComponent,
  ],
})
export class SharedModule {}
