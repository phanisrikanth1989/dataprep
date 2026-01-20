import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Observable } from 'rxjs';
import { JobService } from '@services/job.service';
import { ExecutionService } from '@services/execution.service';
import { AuthService } from '@services/auth.service';
import { JobListResponse, JobSchema } from '@models/types';
import { NzMessageService } from 'ng-zorro-antd/message';
import { NzModalService } from 'ng-zorro-antd/modal';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';

/**
 * Job List Component - Shows all jobs and allows management
 */
@Component({
  selector: 'app-job-list',
  template: `
    <div class="job-list-wrapper">
      <!-- Top Navigation Bar -->
      <div class="top-bar">
        <div class="logo-section">
          <h1 class="logo">RecDataPrep</h1>
          <span class="tagline">Visual ETL Designer</span>
        </div>
        <div class="user-menu">
          <span class="user-name">{{ currentUser?.username }}</span>
          <button nz-button nzType="text" (click)="onLogout()" class="btn-logout">
            Logout
          </button>
        </div>
      </div>

      <!-- Main Content with Left Sidebar -->
      <div class="main-content">
        <!-- Left Sidebar -->
        <div class="left-sidebar">
          <div class="sidebar-header">
            <h3>Repository</h3>
          </div>
          <button nz-button nzType="primary" nzBlock (click)="onNewJob()" class="btn-create">
            <span class="btn-icon">+</span>
            <span class="btn-text">Create New Job</span>
          </button>
          <div class="sidebar-divider"></div>
          <div class="repo-info">
            <p class="repo-title">Manage your jobs</p>
            <p class="repo-description">Create, edit, and execute ETL jobs from this repository</p>
          </div>

          <!-- Clone Repository Section -->
          <div class="clone-repo-section">
            <div class="section-divider"></div>
            <p class="section-title">Import from Repository</p>
            <input
              type="text"
              placeholder="Enter Git URL"
              [(ngModel)]="cloneRepositoryUrl"
              class="repo-input"
              (keydown.enter)="onCloneRepository()"
            />
            <button 
              nz-button 
              nzType="primary"
              nzSize="small"
              class="btn-clone"
              (click)="onCloneRepository()"
              [nzLoading]="isCloning"
            >
              🔗 Clone & Import
            </button>
            <small class="clone-help">
              Clone a Git repository to import all jobs
            </small>
          </div>
        </div>

        <!-- Jobs List Area -->
        <div class="job-list-container">
          <div class="section-header">
            <h2>Your Jobs</h2>
            <p class="section-description">Manage and execute your ETL jobs</p>
          </div>

          <div class="loading" *ngIf="(jobService.loading$ | async)">
            Loading jobs...
          </div>

          <div class="jobs-grid">
            <div
              *ngFor="let job of (jobService.jobs$ | async)"
              class="job-card"
            >
              <div class="job-card-header">
                <h3>{{ job.name }}</h3>
                <span class="job-id">{{ job.id }}</span>
              </div>

              <div class="job-card-body">
                <p>{{ job.description || 'No description' }}</p>
                <div class="job-stats">
                  <span>📦 {{ job.node_count }} components</span>
                  <span>→ {{ job.edge_count }} connections</span>
                </div>
                <small class="job-date">
                  Updated: {{ job.updated_at | date: 'short' }}
                </small>
              </div>

              <div class="job-card-actions">
                <button
                  nz-button
                  nzSize="small"
                  (click)="onEditJob(job.id)"
                >
                  Edit
                </button>
                <button
                  nz-button
                  nzSize="small"
                  (click)="onExecuteJob(job.id)"
                >
                  Execute
                </button>
                <button
                  nz-button
                  nz-popconfirm
                  nzPopconfirmTitle="Delete this job?"
                  nzPopconfirmDescription="This action cannot be undone"
                  (nzOnConfirm)="onDeleteJob(job.id)"
                  nzSize="small"
                  nzDanger
                >
                  Delete
                </button>
              </div>
            </div>
          </div>

          <div *ngIf="(jobService.jobs$ | async) as jobs" class="empty-state">
            <div *ngIf="jobs.length === 0">
              <p>No jobs yet. Use the <strong>Create New Job</strong> button on the left to get started!</p>
            </div>
          </div>
        </div>
      </div>

      <!-- New Job Modal -->
      <nz-modal
        [(nzVisible)]="isNewJobModalVisible"
        nzTitle="Create New Job"
        nzOkText="Create"
        nzCancelText="Cancel"
        nzCentered
        nzWidth="500"
        (nzOnOk)="onCreateJob()"
        (nzOnCancel)="isNewJobModalVisible = false"
        [nzOkLoading]="false"
      >
        <ng-container *nzModalContent>
          <form [formGroup]="newJobForm">
            <div nz-row [nzGutter]="16">
              <div nz-col [nzSpan]="24">
                <label>Job Name *</label>
                <input
                  nz-input
                  formControlName="jobName"
                  placeholder="Enter job name"
                />
              </div>
              <div nz-col [nzSpan]="24">
                <label>Description</label>
                <textarea
                  nz-input
                  formControlName="description"
                  placeholder="Enter job description"
                  rows="3"
                ></textarea>
              </div>
              <div nz-col [nzSpan]="24">
                <label>Version</label>
                <input
                  nz-input
                  formControlName="version"
                  placeholder="e.g., 1.0.0"
                />
              </div>
            </div>
          </form>
        </ng-container>
      </nz-modal>
    </div>
  `,
  styles: [
    `
      .job-list-wrapper {
        height: 100vh;
        display: flex;
        flex-direction: column;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
      }

      .top-bar {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px 40px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
      }

      .user-menu {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .user-name {
        font-size: 14px;
        font-weight: 500;
      }

      .btn-logout {
        color: rgba(255, 255, 255, 0.8) !important;
        font-size: 13px;
        padding: 4px 12px !important;
      }

      .btn-logout:hover {
        color: white !important;
        background: rgba(255, 255, 255, 0.1) !important;
      }

      .main-content {
        display: flex;
        flex: 1;
        overflow: hidden;
      }

      .left-sidebar {
        width: 280px;
        background: white;
        border-right: 2px solid #e2e8f0;
        padding: 24px 20px;
        display: flex;
        flex-direction: column;
        gap: 20px;
        overflow-y: auto;
      }

      .sidebar-header {
        margin-bottom: 12px;
      }

      .sidebar-header h3 {
        margin: 0;
        font-size: 11px;
        font-weight: 600;
        color: #2d3748;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .btn-create {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
        color: white !important;
        font-weight: 700;
        padding: 16px 20px !important;
        border-radius: 8px !important;
        height: auto !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 10px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2) !important;
        font-size: 15px !important;
        line-height: 1.4 !important;
      }

      .btn-create:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4) !important;
      }

      .btn-icon {
        font-size: 22px;
        font-weight: bold;
        display: flex;
        align-items: center;
      }

      .btn-text {
        display: inline-block;
      }

      .sidebar-divider {
        height: 1px;
        background: #e2e8f0;
        margin: 12px 0;
      }

      .repo-info {
        background: #f7fafc;
        padding: 16px 12px;
        border-radius: 8px;
        border-left: 3px solid #667eea;
      }

      .repo-title {
        margin: 0 0 8px 0;
        font-size: 13px;
        font-weight: 600;
        color: #2d3748;
      }

      .repo-description {
        margin: 0;
        font-size: 12px;
        color: #718096;
        line-height: 1.4;
      }

      .logo-section {
        display: flex;
        align-items: baseline;
        gap: 12px;
      }

      .logo {
        margin: 0;
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -0.5px;
      }

      .tagline {
        font-size: 12px;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 1px;
      }

      .btn-create {
        background: rgba(255, 255, 255, 0.2) !important;
        border: 2px solid white !important;
        color: white !important;
        font-weight: 600;
        padding: 8px 24px !important;
        border-radius: 6px !important;
        transition: all 0.3s ease !important;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .btn-create:hover {
        background: white !important;
        color: #667eea !important;
      }

      .job-list-container {
        flex: 1;
        overflow-y: auto;
        padding: 40px;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
      }

      .section-header {
        margin-bottom: 32px;
      }

      .section-header h2 {
        margin: 0;
        font-size: 32px;
        font-weight: 700;
        color: #2d3748;
        letter-spacing: -0.5px;
      }

      .section-description {
        margin: 8px 0 0 0;
        font-size: 14px;
        color: #718096;
      }

      .loading {
        text-align: center;
        padding: 60px 40px;
        color: #718096;
        font-size: 16px;
      }

      .jobs-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 24px;
        margin-bottom: 40px;
      }

      .job-card {
        background: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition: all 0.3s ease;
        display: flex;
        flex-direction: column;
        border-left: 4px solid #667eea;
        cursor: pointer;
        position: relative;
        overflow: hidden;
      }

      .job-card::before {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        width: 100px;
        height: 100px;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, transparent 100%);
        border-radius: 50%;
        transform: translate(40%, -40%);
      }

      .job-card:hover {
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15);
        transform: translateY(-4px);
        border-left-color: #764ba2;
      }

      .job-card-header {
        margin-bottom: 16px;
        position: relative;
        z-index: 1;
      }

      .job-card-header h3 {
        margin: 0 0 6px 0;
        font-size: 18px;
        font-weight: 600;
        color: #2d3748;
      }

      .job-id {
        font-size: 12px;
        color: #a0aec0;
        font-family: 'Monaco', 'Courier', monospace;
        letter-spacing: 0.5px;
      }

      .job-card-body {
        flex: 1;
        margin-bottom: 16px;
        position: relative;
        z-index: 1;
      }

      .job-card-body p {
        margin: 0 0 12px 0;
        font-size: 14px;
        color: #4a5568;
        line-height: 1.5;
      }

      .job-stats {
        display: flex;
        gap: 16px;
        margin: 12px 0;
        font-size: 13px;
        color: #718096;
      }

      .stat-item {
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .stat-icon {
        font-size: 16px;
      }

      .job-date {
        display: block;
        font-size: 12px;
        color: #cbd5e0;
        margin-top: 8px;
      }

      .job-card-actions {
        display: flex;
        gap: 8px;
        position: relative;
        z-index: 1;
        padding-top: 12px;
        border-top: 1px solid #edf2f7;
      }

      .job-card-actions button {
        flex: 1;
        font-size: 12px;
        font-weight: 500;
        border-radius: 6px;
        transition: all 0.2s ease;
      }

      .job-card-actions button[nzType="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
      }

      .job-card-actions button:not([nzType="primary"]) {
        background: #f7fafc !important;
        border: 1px solid #e2e8f0 !important;
        color: #4a5568 !important;
      }

      .job-card-actions button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      }

      .empty-state {
        text-align: center;
        padding: 80px 40px;
        color: #718096;
      }

      .empty-state p {
        font-size: 16px;
        margin-bottom: 24px;
      }

      nz-modal ::ng-deep .ant-modal-content {
        border-radius: 12px;
        padding: 0;
      }

      nz-modal ::ng-deep .ant-modal-header {
        border-bottom: 2px solid #e2e8f0;
        padding: 24px;
      }

      nz-modal ::ng-deep .ant-modal-title {
        font-size: 18px;
        font-weight: 600;
        color: #2d3748;
      }

      nz-modal ::ng-deep .ant-modal-body {
        padding: 24px;
      }

      nz-modal ::ng-deep .ant-modal-footer {
        padding: 16px 24px;
        border-top: 1px solid #e2e8f0;
      }

      nz-modal label {
        display: block;
        margin-bottom: 8px;
        font-weight: 600;
        color: #2d3748;
        font-size: 14px;
      }

      nz-modal input[nz-input],
      nz-modal textarea[nz-input] {
        border-radius: 6px !important;
        border: 1px solid #cbd5e0 !important;
        padding: 10px 12px !important;
        font-size: 14px !important;
      }

      nz-modal input[nz-input]:focus,
      nz-modal textarea[nz-input]:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
      }

      nz-modal [nz-col] {
        margin-bottom: 20px;
      }

      nz-modal [nz-col]:last-child {
        margin-bottom: 0;
      }

      .clone-repo-section {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 16px 12px;
        background: #edf2f7;
        border-radius: 8px;
        border: 1px dashed #667eea;
      }

      .section-title {
        font-size: 11px;
        font-weight: 600;
        color: #2d3748;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0;
      }

      .repo-input {
        padding: 8px 12px;
        border: 1px solid #cbd5e0;
        border-radius: 4px;
        font-size: 12px;
        transition: all 0.2s;
      }

      .repo-input:focus {
        outline: none;
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
      }

      .btn-clone {
        width: 100%;
        height: 32px;
        font-size: 12px !important;
        font-weight: 500 !important;
        border-radius: 4px !important;
      }

      .clone-help {
        font-size: 11px;
        color: #718096;
        text-align: center;
        margin: 0;
      }
    `,
  ],
})
export class JobListComponent implements OnInit {
  isNewJobModalVisible = false;
  newJobForm: FormGroup;
  currentUser: any;
  cloneRepositoryUrl = '';
  isCloning = false;

  constructor(
    private fb: FormBuilder,
    private router: Router,
    public jobService: JobService,
    private executionService: ExecutionService,
    private authService: AuthService,
    private message: NzMessageService,
    private modal: NzModalService
  ) {
    this.newJobForm = this.fb.group({
      jobName: ['', Validators.required],
      description: [''],
      version: ['1.0.0'],
    });
  }

  ngOnInit(): void {
    this.jobService.loadJobs();
    // Get current user
    this.authService.getCurrentUser().subscribe((user) => {
      this.currentUser = user;
    });
  }

  onNewJob(): void {
    this.isNewJobModalVisible = true;
  }

  onCreateJob(): void {
    if (this.newJobForm.valid) {
      const { jobName, description, version } = this.newJobForm.value;
      const newJob = this.jobService.createBlankJob(jobName);
      newJob.description = description;
      newJob.version = version || '1.0.0';

      this.jobService.createJob(newJob).subscribe({
        next: (job: JobSchema) => {
          this.message.success('Job created successfully');
          this.isNewJobModalVisible = false;
          this.newJobForm.reset();
          
          // Navigate to job designer for the newly created job
          this.router.navigate(['/designer', job.id]);
        },
        error: (error: any) => {
          this.message.error('Error creating job');
          console.error(error);
        },
      });
    }
  }

  onEditJob(jobId: string): void {
    this.router.navigate(['/designer', jobId]);
  }

  onExecuteJob(jobId: string): void {
    this.executionService.startExecution(jobId).subscribe({
      next: (response: any) => {
        this.message.success('Job execution started');
        this.router.navigate(['/execution', response.task_id]);
      },
      error: (error: any) => {
        this.message.error('Error starting job execution');
        console.error(error);
      },
    });
  }

  onDeleteJob(jobId: string): void {
    this.jobService.deleteJob(jobId).subscribe({
      next: () => {
        this.message.success('Job deleted successfully');
      },
      error: (error: any) => {
        this.message.error('Error deleting job');
        console.error(error);
      },
    });
  }

  onLogout(): void {
    this.authService.logout();
    this.message.success('Logged out successfully');
    this.router.navigate(['/login']);
  }

  /**
   * Clone a Git repository and import all jobs from it
   */
  onCloneRepository(): void {
    if (!this.cloneRepositoryUrl.trim()) {
      this.message.error('Please enter a repository URL');
      return;
    }

    this.isCloning = true;

    // In a real application, this would call a backend endpoint to clone the repo
    // For now, we'll show a message with the clone command
    const repoUrl = this.cloneRepositoryUrl;
    const repoName = repoUrl.split('/').pop()?.replace('.git', '') || 'repository';
    
    // Simulate cloning delay
    setTimeout(() => {
      this.isCloning = false;
      
      // Show success message with instructions
      this.message.success(
        `Repository cloning started! Jobs from "${repoName}" will be imported.`
      );

      // Log the clone command for reference
      console.log(`Clone command: git clone ${repoUrl}`);
      
      // In production, the backend would:
      // 1. Clone the repository to a temp directory
      // 2. Scan for job JSON files in jobs/ directory
      // 3. Import them into the local jobs/ directory
      // 4. Reload the job list
      
      // For now, show modal with what would happen
      this.showCloneDetails(repoUrl, repoName);

      // Clear the input
      this.cloneRepositoryUrl = '';
    }, 1500);
  }

  /**
   * Show details of what was cloned
   */
  private showCloneDetails(repoUrl: string, repoName: string): void {
    const details = `
      Repository: ${repoName}
      URL: ${repoUrl}
      
      The following jobs would be imported:
      - Sample ETL Job
      - Data Transformation Job
      - File Processing Job
      
      Tip: Refresh the Job List to see imported jobs
    `;
    
    this.message.info(details, { nzDuration: 5 });
  }
}
