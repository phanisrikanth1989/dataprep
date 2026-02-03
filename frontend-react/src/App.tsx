import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import { useStore } from './store';
import Login from './pages/Login';
import JobList from './pages/JobList';
import JobDesignerEnhanced from './pages/JobDesignerEnhanced';
import './App.css';

// Auth guard component
function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

// Modern Zoho-inspired theme
const lightTheme = {
  token: {
    colorPrimary: '#0052CC',
    colorSuccess: '#36B37E',
    colorWarning: '#FFAB00',
    colorError: '#FF5630',
    colorInfo: '#00B8D9',
    colorTextBase: '#172B4D',
    colorBgBase: '#FFFFFF',
    borderRadius: 8,
    fontFamily: "'Open Sans', 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    fontSize: 14,
    controlHeight: 36,
    lineHeight: 1.5,
    wireframe: false,
  },
  components: {
    Button: {
      primaryShadow: '0 2px 4px rgba(0, 82, 204, 0.2)',
      fontWeight: 500,
    },
    Card: {
      borderRadiusLG: 12,
    },
    Input: {
      activeBorderColor: '#0052CC',
      hoverBorderColor: '#4C9AFF',
    },
    Modal: {
      borderRadiusLG: 16,
    },
  },
};

const darkTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#4C9AFF',
    colorSuccess: '#36B37E',
    colorWarning: '#FFAB00',
    colorError: '#FF5630',
    colorInfo: '#00B8D9',
    colorBgBase: '#1a1a2e',
    colorBgContainer: '#16213e',
    colorBgElevated: '#1f3460',
    borderRadius: 8,
    fontFamily: "'Open Sans', 'Source Sans Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    fontSize: 14,
    controlHeight: 36,
    lineHeight: 1.5,
    wireframe: false,
  },
  components: {
    Button: {
      primaryShadow: '0 2px 4px rgba(76, 154, 255, 0.3)',
      fontWeight: 500,
    },
    Card: {
      borderRadiusLG: 12,
    },
    Input: {
      activeBorderColor: '#4C9AFF',
      hoverBorderColor: '#79b8ff',
    },
    Modal: {
      borderRadiusLG: 16,
    },
  },
};

function AppContent() {
  const darkMode = useStore((s) => s.darkMode);

  return (
    <ConfigProvider theme={darkMode ? darkTheme : lightTheme}>
      <div className={darkMode ? 'dark-mode' : 'light-mode'}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <JobList />
              </RequireAuth>
            }
          />
          <Route
            path="/designer/:jobId"
            element={
              <RequireAuth>
                <JobDesignerEnhanced />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </ConfigProvider>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
