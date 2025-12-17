import { useAuth } from '../contexts/AuthContext';
import { useState } from 'react';

export default function Navigation() {
  const { user, logout } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const isAdmin = user?.role === 'admin';
  const isProductOwner = user?.role === 'product_owner';
  const isProductOwnerOrAdmin = isProductOwner || isAdmin;

  return (
    <nav className="bg-white shadow-lg">
      <div className="w-full px-3 sm:px-4 lg:px-6">
        <div className="flex items-center justify-between h-14 sm:h-16">
          {/* Logo - compact on all screens */}
          <div className="flex-shrink-0 flex items-center">
            <a href="/ideas" className="text-lg sm:text-xl font-bold text-blue-600 whitespace-nowrap">
              Feature Voting
            </a>
          </div>

          {/* Main navigation links - horizontal on medium+ screens */}
          <div className="hidden md:flex items-center space-x-1 lg:space-x-2">
            {isProductOwnerOrAdmin && (
              <a
                href="/product-intelligence"
                className="text-gray-700 hover:text-blue-600 hover:bg-blue-50 px-2 lg:px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap"
              >
                Product Intelligence
              </a>
            )}
            <a
              href="/ideas"
              className="text-gray-700 hover:text-blue-600 hover:bg-blue-50 px-2 lg:px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap"
            >
              Browse Ideas
            </a>
            <a
              href="/submit"
              className="text-gray-700 hover:text-blue-600 hover:bg-blue-50 px-2 lg:px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap"
            >
              Submit Idea
            </a>
            {isAdmin && (
              <a
                href="/user-management"
                className="text-gray-700 hover:text-blue-600 hover:bg-blue-50 px-2 lg:px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap"
              >
                User Management
              </a>
            )}
          </div>

          {/* User menu - always visible, compact */}
          <div className="flex items-center flex-shrink-0">
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center space-x-1 sm:space-x-2 text-gray-700 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded-full p-1"
                aria-label="User menu"
              >
                <div className="h-8 w-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-semibold flex-shrink-0">
                  {user?.username?.charAt(0).toUpperCase()}
                </div>
                <svg
                  className={`h-4 w-4 sm:h-5 sm:w-5 transition-transform flex-shrink-0 ${showUserMenu ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              {/* Dropdown menu */}
              {showUserMenu && (
                <>
                  {/* Backdrop */}
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setShowUserMenu(false)}
                  ></div>

                  {/* Menu */}
                  <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-20">
                    <div className="py-1">
                      {/* User info */}
                      <div className="px-4 py-3 border-b border-gray-200">
                        <p className="text-sm font-medium text-gray-900">{user?.username}</p>
                        <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                        <p className="text-xs text-gray-400 mt-1">
                          Role:{' '}
                          <span className="font-medium capitalize">{user?.role}</span>
                        </p>
                      </div>

                      {/* Menu items */}
                      <a
                        href="/profile"
                        className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
                        onClick={() => setShowUserMenu(false)}
                      >
                        <svg
                          className="inline-block w-4 h-4 mr-2"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                          />
                        </svg>
                        My Profile
                      </a>

                      <button
                        onClick={() => {
                          setShowUserMenu(false);
                          logout();
                        }}
                        className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                      >
                        <svg
                          className="inline-block w-4 h-4 mr-2"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                          />
                        </svg>
                        Logout
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Mobile menu - vertical layout for small/medium screens */}
        <div className="md:hidden border-t border-gray-200 pt-2 pb-3 space-y-1">
          {isProductOwnerOrAdmin && (
            <a
              href="/product-intelligence"
              className="block px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-blue-50 transition-colors"
            >
              Product Intelligence
            </a>
          )}
          <a
            href="/ideas"
            className="block px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-blue-50 transition-colors"
          >
            Browse Ideas
          </a>
          <a
            href="/submit"
            className="block px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-blue-50 transition-colors"
          >
            Submit Idea
          </a>
          {isAdmin && (
            <a
              href="/user-management"
              className="block px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-blue-50 transition-colors border-t border-gray-100 mt-2 pt-3"
            >
              User Management
            </a>
          )}
        </div>
      </div>
    </nav>
  );
}
