/**
 * RootRedirect Component
 *
 * Redirects users to their role-appropriate default page:
 * - PO/Admin -> /product-intelligence (Product Dashboard)
 * - Voter -> /ideas
 */

import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { UserRole } from '../types';

export default function RootRedirect() {
  const { user, loading } = useAuth();

  // While auth is loading, show nothing (prevents flash)
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // If not logged in, redirect to login
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // PO and Admin go to Product Dashboard
  if (user.role === UserRole.ADMIN || user.role === UserRole.PRODUCT_OWNER) {
    return <Navigate to="/product-intelligence" replace />;
  }

  // Voters go to Ideas
  return <Navigate to="/ideas" replace />;
}
