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
import { WELCOMED_FLAG } from '../pages/WelcomePage';

export default function RootRedirect() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const isPO = user.role === UserRole.ADMIN || user.role === UserRole.PRODUCT_OWNER;
  const hasSeenWelcome = localStorage.getItem(WELCOMED_FLAG) === '1';

  if (isPO && !hasSeenWelcome) {
    return <Navigate to="/welcome" replace />;
  }

  if (isPO) {
    return <Navigate to="/product-intelligence" replace />;
  }

  return <Navigate to="/ideas" replace />;
}
