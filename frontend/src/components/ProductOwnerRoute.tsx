import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { ReactNode } from 'react';
import { UserRole } from '../types';

/**
 * ProductOwnerRoute
 *
 * Route guard that only allows Product Owners and Admins to access product intelligence routes.
 * Voters are redirected to /ideas.
 */

interface ProductOwnerRouteProps {
  children: ReactNode;
}

export default function ProductOwnerRoute({ children }: ProductOwnerRouteProps) {
  const { user, loading } = useAuth();

  // Show loading state while checking authentication
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Check if user is Product Owner or Admin
  const isProductOwnerOrAdmin = user?.role === UserRole.PRODUCT_OWNER || user?.role === UserRole.ADMIN;

  // Redirect voters to ideas page
  if (!isProductOwnerOrAdmin) {
    return <Navigate to="/ideas" replace />;
  }

  // Render the protected component for Product Owners and Admins
  return <>{children}</>;
}
