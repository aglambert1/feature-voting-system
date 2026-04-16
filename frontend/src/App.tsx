/**
 * App Component
 *
 * Main application component with:
 * - React Router setup
 * - AuthProvider wrapper
 * - Route definitions
 * - Protected routes
 */

import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
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
import JobMapEditorPage from './pages/CompetitorIntelligence/JobMapEditorPage';
import ProductDashboardPage from './pages/ProductDashboardPage';
import IntelligenceHubPage from './pages/CompetitorIntelligence/IntelligenceHubPage';
import InternalFeedbackPage from './pages/CompetitorIntelligence/InternalFeedbackPage';
import SynthesisHubPage from './pages/CompetitorIntelligence/SynthesisHubPage';
import EvidencePage from './pages/CompetitorIntelligence/EvidencePage';
import IdeaLifecycleSettingsPage from './pages/IdeaLifecycleSettingsPage';
import JoinPage from './pages/JoinPage';

// Redirect from old /report route to new V2 IntelligenceHub
function ReportRedirect() {
  const { productId } = useParams<{ productId: string }>();
  return <Navigate to={`/product-intelligence/products/${productId}/intelligence?tab=competitor-reports`} replace />;
}

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
          <Route path="/join/:code" element={<JoinPage />} />
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

          <Route
            path="/admin/idea-settings"
            element={
              <ProtectedRoute>
                <AdminRoute>
                  <IdeaLifecycleSettingsPage />
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
          {/* Legacy route - redirect to V2 IntelligenceHub */}
          <Route
            path="/product-intelligence/products/:productId/report"
            element={<ReportRedirect />}
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
          <Route
            path="/product-intelligence/products/:productId/job-map"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <JobMapEditorPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId/internal-feedback"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <InternalFeedbackPage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId/evidence"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <EvidencePage />
                </ProductOwnerRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/product-intelligence/products/:productId/synthesis"
            element={
              <ProtectedRoute>
                <ProductOwnerRoute>
                  <SynthesisHubPage />
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
