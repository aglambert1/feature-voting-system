# Module 2: Product Management API & UI

## Objective
Create the product management system (CRUD operations) with backend API and frontend UI for listing and managing products.

## Dependencies
- **Requires**: Module 1 (Database Schema & Models) completed
- **Uses**: Existing authentication system, existing React components

## Scope
- Product service layer (business logic)
- Product API endpoints (REST)
- Product List page (frontend)
- Product Detail page (frontend)
- Basic product management (create, read, update, archive)

## Backend Implementation

### 1. Product Service

Location: `app/services/product_service.py`

```python
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.competitor_intelligence import CIProduct
from app.schemas.competitor_intelligence import ProductCreate, ProductUpdate, ProductResponse

class ProductService:
    """Service for managing CI products"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_product(
        self, 
        user_id: UUID, 
        product_data: ProductCreate
    ) -> Tuple[CIProduct, bool]:
        """
        Create a new product or return existing if name already exists
        Returns: (product, is_new)
        """
        # Check if product with this name already exists for user
        existing = self.db.query(CIProduct).filter(
            CIProduct.user_id == user_id,
            CIProduct.product_name == product_data.product_name
        ).first()
        
        if existing:
            return existing, False
        
        # Create new product
        product = CIProduct(
            user_id=user_id,
            product_name=product_data.product_name,
            product_description=product_data.product_description,
            status="active"
        )
        
        try:
            self.db.add(product)
            self.db.commit()
            self.db.refresh(product)
            return product, True
        except IntegrityError:
            self.db.rollback()
            # Race condition - another request created the same product
            existing = self.db.query(CIProduct).filter(
                CIProduct.user_id == user_id,
                CIProduct.product_name == product_data.product_name
            ).first()
            return existing, False
    
    async def list_user_products(
        self, 
        user_id: UUID,
        include_archived: bool = False
    ) -> List[CIProduct]:
        """Get all products for a user"""
        query = self.db.query(CIProduct).filter(CIProduct.user_id == user_id)
        
        if not include_archived:
            query = query.filter(CIProduct.status == "active")
        
        return query.order_by(CIProduct.last_analyzed_at.desc().nullslast()).all()
    
    async def get_product(
        self, 
        product_id: UUID, 
        user_id: UUID
    ) -> Optional[CIProduct]:
        """Get a single product by ID (with user ownership check)"""
        return self.db.query(CIProduct).filter(
            CIProduct.id == product_id,
            CIProduct.user_id == user_id
        ).first()
    
    async def update_product(
        self, 
        product_id: UUID, 
        user_id: UUID, 
        update_data: ProductUpdate
    ) -> Optional[CIProduct]:
        """Update product details"""
        product = await self.get_product(product_id, user_id)
        
        if not product:
            return None
        
        # Update fields
        if update_data.product_name is not None:
            product.product_name = update_data.product_name
        if update_data.product_description is not None:
            product.product_description = update_data.product_description
        if update_data.status is not None:
            product.status = update_data.status
        
        product.updated_at = datetime.utcnow()
        
        try:
            self.db.commit()
            self.db.refresh(product)
            return product
        except IntegrityError:
            self.db.rollback()
            return None  # Duplicate name
    
    async def archive_product(
        self, 
        product_id: UUID, 
        user_id: UUID
    ) -> bool:
        """Archive (soft delete) a product"""
        product = await self.get_product(product_id, user_id)
        
        if not product:
            return False
        
        product.status = "archived"
        product.updated_at = datetime.utcnow()
        self.db.commit()
        return True
    
    async def get_product_summary(
        self, 
        product_id: UUID, 
        user_id: UUID
    ) -> Optional[dict]:
        """Get product with session statistics"""
        product = await self.get_product(product_id, user_id)
        
        if not product:
            return None
        
        return {
            "id": product.id,
            "product_name": product.product_name,
            "product_description": product.product_description,
            "product_category": product.product_category,
            "analysis_count": product.analysis_count,
            "last_analyzed_at": product.last_analyzed_at,
            "status": product.status,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "sessions": [
                {
                    "id": session.id,
                    "session_number": session.session_number,
                    "session_name": session.session_name,
                    "status": session.status,
                    "created_at": session.created_at,
                    "completed_at": session.completed_at
                }
                for session in product.sessions
            ]
        }
```

### 2. Product API Endpoints

Location: `app/routers/products.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
from app.schemas.competitor_intelligence import (
    ProductCreate, ProductUpdate, ProductResponse
)
from app.services.product_service import ProductService
from app.dependencies import get_current_user, get_db
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/competitor-intelligence/products",
    tags=["products"]
)

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new product for competitor analysis"""
    service = ProductService(db)
    product, is_new = await service.create_product(current_user.id, product_data)
    
    return product

@router.get("", response_model=List[ProductResponse])
async def list_products(
    include_archived: bool = False,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all products for the current user"""
    service = ProductService(db)
    products = await service.list_user_products(current_user.id, include_archived)
    
    return products

@router.get("/{product_id}", response_model=dict)
async def get_product(
    product_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a product with its session history"""
    service = ProductService(db)
    product_summary = await service.get_product_summary(product_id, current_user.id)
    
    if not product_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return product_summary

@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    update_data: ProductUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update product details"""
    service = ProductService(db)
    product = await service.update_product(product_id, current_user.id, update_data)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or name already exists"
        )
    
    return product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_product(
    product_id: UUID,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Archive a product (soft delete)"""
    service = ProductService(db)
    success = await service.archive_product(product_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return None
```

**Register Router:**
In `app/main.py`:
```python
from app.routers import products

app.include_router(products.router)
```

## Frontend Implementation

### 1. Product List Page

Location: `src/pages/CompetitorIntelligence/ProductList.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import ProductCard from './components/ProductCard';

interface Product {
  id: string;
  product_name: string;
  product_description: string;
  product_category: string | null;
  analysis_count: number;
  last_analyzed_at: string | null;
  status: string;
  created_at: string;
}

const ProductList: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/competitor-intelligence/products');
      setProducts(response.data);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  const handleNewAnalysis = () => {
    navigate('/competitor-intelligence/wizard');
  };

  const handleViewProduct = (productId: string) => {
    navigate(`/competitor-intelligence/products/${productId}`);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-600">Loading products...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Competitor Intelligence
        </h1>
        <button
          onClick={handleNewAnalysis}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          + New Product Analysis
        </button>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {products.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-gray-500 mb-4">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No products yet
          </h3>
          <p className="text-gray-500 mb-4">
            Get started by creating your first competitor analysis
          </p>
          <button
            onClick={handleNewAnalysis}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Create First Analysis
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onClick={() => handleViewProduct(product.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default ProductList;
```

### 2. Product Card Component

Location: `src/pages/CompetitorIntelligence/components/ProductCard.tsx`

```typescript
import React from 'react';
import { formatDistanceToNow } from 'date-fns';

interface ProductCardProps {
  product: {
    id: string;
    product_name: string;
    product_description: string;
    analysis_count: number;
    last_analyzed_at: string | null;
  };
  onClick: () => void;
}

const ProductCard: React.FC<ProductCardProps> = ({ product, onClick }) => {
  return (
    <div
      onClick={onClick}
      className="bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow cursor-pointer border border-gray-200"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center">
          <div className="bg-blue-100 p-2 rounded-lg mr-3">
            <svg
              className="w-6 h-6 text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900">
            {product.product_name}
          </h3>
        </div>
      </div>

      <p className="text-gray-600 text-sm mb-4 line-clamp-2">
        {product.product_description}
      </p>

      <div className="flex items-center justify-between text-sm">
        <div className="text-gray-500">
          {product.analysis_count} {product.analysis_count === 1 ? 'analysis' : 'analyses'}
        </div>
        {product.last_analyzed_at && (
          <div className="text-gray-500">
            {formatDistanceToNow(new Date(product.last_analyzed_at), {
              addSuffix: true,
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProductCard;
```

### 3. Product Detail Page

Location: `src/pages/CompetitorIntelligence/ProductDetail.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { formatDistanceToNow } from 'date-fns';

interface Session {
  id: string;
  session_number: number;
  session_name: string | null;
  status: string;
  created_at: string;
  completed_at: string | null;
}

interface ProductDetail {
  id: string;
  product_name: string;
  product_description: string;
  product_category: string | null;
  analysis_count: number;
  last_analyzed_at: string | null;
  status: string;
  created_at: string;
  sessions: Session[];
}

const ProductDetail: React.FC = () => {
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (productId) {
      fetchProduct();
    }
  }, [productId]);

  const fetchProduct = async () => {
    try {
      setLoading(true);
      const response = await axios.get(
        `/api/competitor-intelligence/products/${productId}`
      );
      setProduct(response.data);
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to load product');
    } finally {
      setLoading(false);
    }
  };

  const handleStartNewAnalysis = () => {
    navigate(`/competitor-intelligence/wizard?product_id=${productId}`);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-600">Loading product...</div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error || 'Product not found'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <button
          onClick={() => navigate('/competitor-intelligence')}
          className="text-blue-600 hover:text-blue-800 mb-4"
        >
          ← Back to Products
        </button>
        
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {product.product_name}
            </h1>
            {product.product_category && (
              <span className="inline-block px-3 py-1 bg-blue-100 text-blue-800 text-sm rounded-full">
                {product.product_category}
              </span>
            )}
          </div>
          <button
            onClick={handleStartNewAnalysis}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Start New Analysis
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          Product Description
        </h2>
        <p className="text-gray-700">{product.product_description}</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Analysis History ({product.analysis_count})
        </h2>
        
        {product.sessions.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500 mb-4">No analyses yet</p>
            <button
              onClick={handleStartNewAnalysis}
              className="text-blue-600 hover:text-blue-800"
            >
              Start your first analysis
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {product.sessions.map((session) => (
              <div
                key={session.id}
                className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h3 className="font-medium text-gray-900">
                      Analysis #{session.session_number}
                      {session.session_name && ` - ${session.session_name}`}
                    </h3>
                    <p className="text-sm text-gray-500">
                      Started {formatDistanceToNow(new Date(session.created_at), {
                        addSuffix: true,
                      })}
                    </p>
                  </div>
                  <span
                    className={`px-2 py-1 text-xs rounded-full ${
                      session.status === 'completed'
                        ? 'bg-green-100 text-green-800'
                        : session.status === 'active'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {session.status}
                  </span>
                </div>
                {session.completed_at && (
                  <p className="text-sm text-gray-500">
                    Completed {formatDistanceToNow(new Date(session.completed_at), {
                      addSuffix: true,
                    })}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProductDetail;
```

### 4. Add Routes

Location: `src/App.tsx` (or routing file)

```typescript
import ProductList from './pages/CompetitorIntelligence/ProductList';
import ProductDetail from './pages/CompetitorIntelligence/ProductDetail';

// Add to routes:
<Route path="/competitor-intelligence" element={<ProductList />} />
<Route path="/competitor-intelligence/products/:productId" element={<ProductDetail />} />
```

## Testing Requirements

### Backend Unit Tests

Location: `tests/test_product_service.py`

```python
import pytest
from app.services.product_service import ProductService
from app.schemas.competitor_intelligence import ProductCreate, ProductUpdate

@pytest.mark.asyncio
async def test_create_product(db_session, test_user):
    """Test creating a new product"""
    service = ProductService(db_session)
    product_data = ProductCreate(
        product_name="Test Product",
        product_description="This is a test product",
        product_source_type="text"
    )
    
    product, is_new = await service.create_product(test_user.id, product_data)
    
    assert is_new is True
    assert product.product_name == "Test Product"
    assert product.user_id == test_user.id

@pytest.mark.asyncio
async def test_create_duplicate_product(db_session, test_user):
    """Test that creating duplicate product returns existing"""
    service = ProductService(db_session)
    product_data = ProductCreate(
        product_name="Same Name",
        product_description="First",
        product_source_type="text"
    )
    
    product1, is_new1 = await service.create_product(test_user.id, product_data)
    product2, is_new2 = await service.create_product(test_user.id, product_data)
    
    assert is_new1 is True
    assert is_new2 is False
    assert product1.id == product2.id

@pytest.mark.asyncio
async def test_list_user_products(db_session, test_user):
    """Test listing products for user"""
    service = ProductService(db_session)
    
    # Create 2 products
    for i in range(2):
        product_data = ProductCreate(
            product_name=f"Product {i}",
            product_description=f"Description {i}",
            product_source_type="text"
        )
        await service.create_product(test_user.id, product_data)
    
    products = await service.list_user_products(test_user.id)
    
    assert len(products) == 2
```

### Backend Integration Tests

Location: `tests/test_product_api.py`

```python
import pytest
from fastapi.testclient import TestClient

def test_create_product_api(client: TestClient, auth_headers):
    """Test product creation via API"""
    response = client.post(
        "/api/competitor-intelligence/products",
        json={
            "product_name": "API Test Product",
            "product_description": "Created via API",
            "product_source_type": "text"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["product_name"] == "API Test Product"
    assert "id" in data

def test_list_products_api(client: TestClient, auth_headers):
    """Test listing products via API"""
    response = client.get(
        "/api/competitor-intelligence/products",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_product_detail_api(client: TestClient, auth_headers, test_product):
    """Test getting product detail via API"""
    response = client.get(
        f"/api/competitor-intelligence/products/{test_product.id}",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_product.id)
    assert "sessions" in data
```

### Frontend Manual Testing

1. **Navigate to product list page**
   - Should show empty state if no products
   - "New Product Analysis" button should be visible

2. **Create product flow** (will be completed in Module 4)
   - For now, create products via API/database

3. **View product list**
   - Products should display in cards
   - Should show analysis count, last analyzed date
   - Click should navigate to detail page

4. **View product detail**
   - Should show product info
   - Should show session history (empty for now)
   - "Start New Analysis" button should be visible

## Acceptance Criteria

**Backend:**
- [ ] Can create products via API
- [ ] Duplicate product names for same user return existing product
- [ ] Can list all products for a user
- [ ] Can get product detail with session list
- [ ] Can update product name/description
- [ ] Can archive product
- [ ] All endpoints require authentication
- [ ] All unit tests pass
- [ ] All integration tests pass

**Frontend:**
- [ ] Product list page displays correctly
- [ ] Empty state shows for new users
- [ ] Product cards display all info correctly
- [ ] Can navigate to product detail page
- [ ] Product detail shows product info and session history
- [ ] Loading and error states work correctly
- [ ] Responsive design works on mobile

## Files to Create/Modify

**New Files:**
- `app/services/product_service.py`
- `app/routers/products.py`
- `src/pages/CompetitorIntelligence/ProductList.tsx`
- `src/pages/CompetitorIntelligence/ProductDetail.tsx`
- `src/pages/CompetitorIntelligence/components/ProductCard.tsx`
- `tests/test_product_service.py`
- `tests/test_product_api.py`

**Modified Files:**
- `app/main.py` (register router)
- `src/App.tsx` (add routes)

## Estimated Time
**2-3 days** including testing

## Next Module
After completing this module, proceed to **Module 3: Base Agent Infrastructure**
