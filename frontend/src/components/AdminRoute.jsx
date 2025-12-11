import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

/**
 * AdminRoute
 *
 * Route guard that only allows admin users to access certain routes.
 * Non-admin users are redirected to /ideas.
 */
export default function AdminRoute({ children }) {
  const { user, loading } = useAuth();

  // Show loading state while checking authentication
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Check if user is admin
  const isAdmin = user?.role === 'admin';

  // Redirect non-admin users to ideas page
  if (!isAdmin) {
    return <Navigate to="/ideas" replace />;
  }

  // Render the protected component for admin users
  return children;
}
