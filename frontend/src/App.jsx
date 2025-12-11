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
import AdminRoute from './components/AdminRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import IdeasPage from './pages/IdeasPage';
import SubmitIdeaPage from './pages/SubmitIdeaPage';
import ProfilePage from './pages/ProfilePage';
import UserManagementPage from './pages/UserManagementPage';
import ProductListPage from './pages/CompetitorIntelligence/ProductListPage';
import CreateProductPage from './pages/CompetitorIntelligence/CreateProductPage';
import AnalyzeProductPage from './pages/CompetitorIntelligence/AnalyzeProductPage';
import ProductDetailPage from './pages/CompetitorIntelligence/ProductDetailPage';
import SessionWorkflowPage from './pages/CompetitorIntelligence/SessionWorkflowPage';

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
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/user-management"
            element={
              <ProtectedRoute>
                <AdminRoute>
                  <UserManagementPage />
                </AdminRoute>
              </ProtectedRoute>
            }
          />

          {/* Competitor Intelligence routes */}
          <Route
            path="/competitor-intelligence"
            element={
              <ProtectedRoute>
                <ProductListPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/competitor-intelligence/products/create"
            element={
              <ProtectedRoute>
                <CreateProductPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/competitor-intelligence/products/:productId"
            element={
              <ProtectedRoute>
                <ProductDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/competitor-intelligence/products/:productId/analyze"
            element={
              <ProtectedRoute>
                <AnalyzeProductPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/competitor-intelligence/products/:productId/sessions/:sessionId"
            element={
              <ProtectedRoute>
                <SessionWorkflowPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/competitor-intelligence/products/:productId/sessions"
            element={
              <ProtectedRoute>
                <SessionWorkflowPage />
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
