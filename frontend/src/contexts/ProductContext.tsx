import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import api from '../services/api';

export interface ProductListItem {
  id: number;
  product_name: string;
}

interface ProductContextType {
  products: ProductListItem[];
  selectedProductId: number | 'all' | null;
  setSelectedProductId: (id: number | 'all' | null) => void;
  loadingProducts: boolean;
  hasProducts: boolean;
  getProductName: (id: number) => string | null;
}

const ProductContext = createContext<ProductContextType | undefined>(undefined);

export const ProductProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | 'all' | null>(() => {
    // Initialize from sessionStorage if available
    const stored = sessionStorage.getItem('selectedProductId');
    if (stored === 'all') return 'all';
    if (stored === null || stored === 'null') return null;
    const parsed = parseInt(stored, 10);
    return isNaN(parsed) ? 'all' : parsed;
  });
  const [loadingProducts, setLoadingProducts] = useState<boolean>(true);
  const [hasProducts, setHasProducts] = useState<boolean>(true);

  // Fetch products on mount and when user logs in
  useEffect(() => {
    const fetchProducts = async () => {
      // Check if user has a token (is logged in)
      const token = localStorage.getItem('access_token');

      if (!token) {
        // User not logged in - skip fetching products
        setLoadingProducts(false);
        setProducts([]);
        setHasProducts(false);
        return;
      }

      try {
        setLoadingProducts(true);
        const response = await api.get('/ideas/products');
        // API returns array directly, not an object with products property
        const fetchedProducts = Array.isArray(response.data) ? response.data : [];
        setProducts(fetchedProducts);
        setHasProducts(fetchedProducts.length > 0);

        // If we have a stored selection, validate it still exists
        const storedId = selectedProductId;
        if (storedId !== 'all' && storedId !== null) {
          const productExists = fetchedProducts.some((p: ProductListItem) => p.id === storedId);
          if (!productExists) {
            // Reset to 'all' if stored product no longer exists
            setSelectedProductId('all');
            sessionStorage.setItem('selectedProductId', 'all');
          }
        }
      } catch (error) {
        console.error('Failed to fetch products:', error);
        setProducts([]);
        setHasProducts(false);
      } finally {
        setLoadingProducts(false);
      }
    };

    // Initial fetch
    fetchProducts();

    // Listen for storage events (when token is added/removed in another tab)
    // Also create a custom event for same-tab login
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'access_token') {
        fetchProducts();
      }
    };

    const handleLogin = () => {
      fetchProducts();
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('user-logged-in', handleLogin);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('user-logged-in', handleLogin);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount

  // Persist selection to sessionStorage whenever it changes
  useEffect(() => {
    if (selectedProductId === null) {
      sessionStorage.setItem('selectedProductId', 'null');
    } else {
      sessionStorage.setItem('selectedProductId', selectedProductId.toString());
    }
  }, [selectedProductId]);

  const getProductName = (id: number): string | null => {
    const product = products.find(p => p.id === id);
    return product ? product.product_name : null;
  };

  return (
    <ProductContext.Provider
      value={{
        products,
        selectedProductId,
        setSelectedProductId,
        loadingProducts,
        hasProducts,
        getProductName,
      }}
    >
      {children}
    </ProductContext.Provider>
  );
};

export const useProduct = (): ProductContextType => {
  const context = useContext(ProductContext);
  if (!context) {
    throw new Error('useProduct must be used within a ProductProvider');
  }
  return context;
};
