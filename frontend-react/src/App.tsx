import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import { useStore } from './store';
import Login from './pages/Login';
import JobList from './pages/JobList';
import JobDesigner from './pages/JobDesigner';
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
const zohoTheme = {
  token: {
    colorPrimary: '#0052CC',
    colorSuccess: '#36B37E',
    colorWarning: '#FFAB00',
    colorError: '#FF5630',
    colorInfo: '#00B8D9',
    colorTextBase: '#172B4D',
    colorBgBase: '#FFFFFF',
    borderRadius: 8,
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
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

function App() {
  return (
    <ConfigProvider theme={zohoTheme}>
      <BrowserRouter>
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
                <JobDesigner />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
