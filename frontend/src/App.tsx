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
import { ProductProvider } from './contexts/ProductContext';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import ProductOwnerRoute from './components/ProductOwnerRoute';
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
import ReviewQueuePage from './pages/ReviewQueuePage';
import ProductDashboardPage from './pages/ProductDashboardPage';

function App() {
  return (
    <Router>
      <AuthProvider>
        <ProductProvider>
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

          {/* Product Intelligence routes - restricted to Product Owners and Admins */}
          <Route
            path="/product-intelligence"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <ProductListPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/create"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <CreateProductPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <ProductDetailPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId/analyze"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <AnalyzeProductPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId/sessions/:sessionId"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <SessionWorkflowPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId/sessions"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <SessionWorkflowPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId/dashboard"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <ProductDashboardPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />

          {/* Review Queue - restricted to Product Owners and Admins */}
          <Route
            path="/review-queue"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <ReviewQueuePage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />

          {/* 404 - redirect to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </ProductProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
