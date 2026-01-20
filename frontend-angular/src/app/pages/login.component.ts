import { Component, OnInit } from '@angular/core';
import { Router, ActivatedRoute } from '@angular/router';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AuthService } from '@services/auth.service';
import { NzMessageService } from 'ng-zorro-antd/message';

@Component({
  selector: 'app-login',
  template: `
    <div class="login-wrapper">
      <!-- Background Animation -->
      <div class="gradient-bg">
        <div class="shape shape-1"></div>
        <div class="shape shape-2"></div>
        <div class="shape shape-3"></div>
      </div>

      <!-- Login Card -->
      <div class="login-card">
        <!-- Logo Section -->
        <div class="logo-section">
          <div class="logo-icon">⚡</div>
          <h1>RecDataPrep</h1>
          <p>Visual ETL Data Processing</p>
        </div>

        <!-- Login Form -->
        <form [formGroup]="loginForm" (ngSubmit)="onLogin()" class="login-form">
          <!-- Username Field -->
          <div class="form-group">
            <label for="username" class="form-label">Username</label>
            <input
              id="username"
              nz-input
              formControlName="username"
              placeholder="Enter your username"
              class="form-input"
              [class.error]="isSubmitted && loginForm.get('username')?.hasError('required')"
              (keyup.enter)="onLogin()"
              autocomplete="username"
            />
            <div *ngIf="isSubmitted && loginForm.get('username')?.hasError('required')" class="error-message">
              Username is required
            </div>
          </div>

          <!-- Password Field -->
          <div class="form-group">
            <label for="password" class="form-label">Password</label>
            <input
              id="password"
              nz-input
              type="password"
              formControlName="password"
              placeholder="Enter your password"
              class="form-input"
              [class.error]="isSubmitted && loginForm.get('password')?.hasError('required')"
              (keyup.enter)="onLogin()"
              autocomplete="current-password"
            />
            <div *ngIf="isSubmitted && loginForm.get('password')?.hasError('required')" class="error-message">
              Password is required
            </div>
          </div>

          <!-- Remember Me -->
          <div class="remember-me">
            <input type="checkbox" id="remember" />
            <label for="remember">Remember me</label>
          </div>

          <!-- Error Message -->
          <div *ngIf="errorMessage" class="alert-error">
            <span class="icon">⚠️</span>
            <span>{{ errorMessage }}</span>
          </div>

          <!-- Login Button -->
          <button
            type="submit"
            nz-button
            nzType="primary"
            class="login-button"
            [disabled]="isLoading"
            [nzLoading]="isLoading"
          >
            <span *ngIf="!isLoading">Sign In</span>
            <span *ngIf="isLoading">Signing in...</span>
          </button>
        </form>

        <!-- Demo Credentials Info -->
        <div class="demo-info">
          <p class="demo-title">Demo Credentials</p>
          <div class="credentials">
            <div class="credential-item">
              <span class="label">Username:</span>
              <span class="value">admin</span>
            </div>
            <div class="credential-item">
              <span class="label">Password:</span>
              <span class="value">admin123</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="login-footer">
        <p>RecDataPrep © 2026. All rights reserved.</p>
      </div>
    </div>
  `,
  styles: [
    `
      .login-wrapper {
        height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        position: relative;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      }

      .gradient-bg {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        z-index: 0;
      }

      .shape {
        position: absolute;
        border-radius: 50%;
        opacity: 0.1;
      }

      .shape-1 {
        width: 300px;
        height: 300px;
        background: white;
        top: -100px;
        right: -50px;
        animation: float 6s ease-in-out infinite;
      }

      .shape-2 {
        width: 200px;
        height: 200px;
        background: white;
        bottom: -50px;
        left: 10%;
        animation: float 8s ease-in-out infinite 1s;
      }

      .shape-3 {
        width: 150px;
        height: 150px;
        background: white;
        bottom: 20%;
        right: 10%;
        animation: float 7s ease-in-out infinite 2s;
      }

      @keyframes float {
        0%, 100% {
          transform: translateY(0px);
        }
        50% {
          transform: translateY(20px);
        }
      }

      .login-card {
        background: white;
        border-radius: 16px;
        padding: 48px 40px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        width: 100%;
        max-width: 420px;
        z-index: 1;
        animation: slideUp 0.5s ease-out;
      }

      @keyframes slideUp {
        from {
          opacity: 0;
          transform: translateY(30px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      .logo-section {
        text-align: center;
        margin-bottom: 32px;
      }

      .logo-icon {
        font-size: 48px;
        margin-bottom: 12px;
        display: inline-block;
        animation: pulse 2s ease-in-out infinite;
      }

      @keyframes pulse {
        0%, 100% {
          transform: scale(1);
        }
        50% {
          transform: scale(1.1);
        }
      }

      .logo-section h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        color: #2d3748;
        letter-spacing: -0.5px;
      }

      .logo-section p {
        margin: 8px 0 0 0;
        font-size: 13px;
        color: #718096;
        letter-spacing: 0.5px;
        text-transform: uppercase;
      }

      .login-form {
        margin-bottom: 24px;
      }

      .form-group {
        margin-bottom: 20px;
      }

      .form-label {
        display: block;
        margin-bottom: 8px;
        font-size: 14px;
        font-weight: 600;
        color: #2d3748;
      }

      .form-input {
        width: 100% !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
        border-radius: 8px !important;
        border: 2px solid #e2e8f0 !important;
        transition: all 0.3s ease !important;
      }

      .form-input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
      }

      .form-input.error {
        border-color: #f56565 !important;
      }

      .error-message {
        margin-top: 6px;
        font-size: 12px;
        color: #f56565;
        font-weight: 500;
      }

      .remember-me {
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        color: #4a5568;
      }

      .remember-me input {
        cursor: pointer;
        width: 16px;
        height: 16px;
      }

      .remember-me label {
        cursor: pointer;
        margin: 0;
      }

      .alert-error {
        background: #fff5f5;
        border: 1px solid #feb2b2;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
        color: #c53030;
      }

      .alert-error .icon {
        font-size: 18px;
      }

      .login-button {
        width: 100% !important;
        height: 44px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: none !important;
        transition: all 0.3s ease !important;
      }

      .login-button:hover:not([disabled]) {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4) !important;
      }

      .login-button[disabled] {
        opacity: 0.7;
        cursor: not-allowed;
      }

      .demo-info {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        margin-top: 24px;
      }

      .demo-title {
        margin: 0 0 12px 0;
        font-size: 12px;
        font-weight: 600;
        color: #2d3748;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .credentials {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .credential-item {
        display: flex;
        justify-content: space-between;
        font-size: 13px;
      }

      .credential-item .label {
        color: #718096;
        font-weight: 500;
      }

      .credential-item .value {
        color: #2d3748;
        font-family: 'Monaco', 'Courier', monospace;
        font-weight: 600;
      }

      .login-footer {
        position: absolute;
        bottom: 24px;
        left: 0;
        right: 0;
        text-align: center;
        color: rgba(255, 255, 255, 0.8);
        font-size: 12px;
        z-index: 1;
      }

      .login-footer p {
        margin: 0;
      }

      @media (max-width: 480px) {
        .login-card {
          margin: 20px;
          padding: 32px 24px;
          max-width: none;
        }

        .logo-icon {
          font-size: 40px;
        }

        .logo-section h1 {
          font-size: 24px;
        }
      }
    `,
  ],
})
export class LoginComponent implements OnInit {
  loginForm: FormGroup;
  isLoading = false;
  isSubmitted = false;
  errorMessage = '';
  returnUrl = '';
  isSetupGuideVisible = false;

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router,
    private route: ActivatedRoute,
    private message: NzMessageService
  ) {
    this.loginForm = this.fb.group({
      username: ['', Validators.required],
      password: ['', Validators.required],
    });
  }

  ngOnInit(): void {
    // Get return URL from route parameters or default to '/'
    this.returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/';

    // If already logged in, redirect to home
    if (this.authService.isAuthenticatedSync()) {
      this.router.navigate([this.returnUrl]);
    }
  }

  onLogin(): void {
    this.isSubmitted = true;
    this.errorMessage = '';

    if (this.loginForm.invalid) {
      return;
    }

    this.isLoading = true;
    const { username, password } = this.loginForm.value;

    this.authService.login(username, password).subscribe({
      next: () => {
        this.isLoading = false;
        this.message.success('Login successful! Welcome admin.');
        this.router.navigate([this.returnUrl]);
      },
      error: (error) => {
        this.isLoading = false;
        this.errorMessage = error.message || 'Invalid username or password';
      },
    });
  }
}
