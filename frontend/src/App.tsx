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
import RootRedirect from './components/RootRedirect';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import IdeasPage from './pages/IdeasPage';
import IdeaDetailPage from './pages/IdeaDetailPage';
import SubmitIdeaPage from './pages/SubmitIdeaPage';
import ProfilePage from './pages/ProfilePage';
import UserManagementPage from './pages/UserManagementPage';
import ProductListPage from './pages/CompetitorIntelligence/ProductListPage';
import CreateProductPage from './pages/CompetitorIntelligence/CreateProductPage';
import AnalyzeProductPage from './pages/CompetitorIntelligence/AnalyzeProductPage';
import ProductDetailPage from './pages/CompetitorIntelligence/ProductDetailPage';
import CompetitorsPage from './pages/CompetitorIntelligence/CompetitorsPage';
import CompetitiveReportPage from './pages/CompetitorIntelligence/CompetitiveReportPage';
// Legacy pages - kept for hidden route access
import SessionWorkflowPage from './pages/CompetitorIntelligence/SessionWorkflowPage';
import ProductDashboardPage from './pages/ProductDashboardPage';
import IntelligenceHubPage from './pages/CompetitorIntelligence/IntelligenceHubPage';

function App() {
  return (
    <Router>
      <AuthProvider>
        <ProductProvider>
          <Routes>
          {/* Root - role-aware redirect */}
          <Route path="/" element={<RootRedirect />} />

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
            path="/ideas/:ideaId"
            element={
              <ProtectedRoute>
                <IdeaDetailPage />
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
            path="/product-intelligence/products/:productId/competitors"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <CompetitorsPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId/report"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <CompetitiveReportPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          {/* Legacy routes - hidden from navigation but still accessible */}
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
          <Route
            path="/product-intelligence/products/:productId/intelligence"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <IntelligenceHubPage />
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
