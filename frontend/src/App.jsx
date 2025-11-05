/**
 * App Component
 *
 * Main application component with:
 * - React Router setup
 * - AuthProvider wrapper
 * - Route definitions
 * - Protected routes
 */

import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import IdeasPage from './pages/IdeasPage';
import SubmitIdeaPage from './pages/SubmitIdeaPage';

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          {/* Root - redirect to ideas */}
          <Route path="/" element={<Navigate to="/ideas" replace />} />

          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes */}
          <Route
            path="/ideas"
            element={
              <ProtectedRoute>
                <IdeasPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/submit"
            element={
              <ProtectedRoute>
                <SubmitIdeaPage />
              </ProtectedRoute>
            }
          />

          {/* 404 - redirect to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
