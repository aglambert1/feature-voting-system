"""
Products API endpoints for Competitor Intelligence.

This module provides REST API endpoints for managing CI products independently
of analysis sessions. Products are shared team resources with permission-based access.

Independent Stages:
- Stage 0: Create Product (no analysis)
- Stage 1: Analyze Product (independent, can be run multiple times)
- Stage 2: Discover Competitors (handled by sessions)
- Stage 3: Analyze Competitor Features (handled by sessions)
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body, Request, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid
from pathlib import Path

from app.database import get_db
from app.models.user import User
from app.models.competitor_intelligence import ProductPermissionLevel
from app.services.product_service import ProductService
from app.services.llm_service import llm_service
from app.services.document_parsing_service import DocumentParsingService
from app.services.vector_service import VectorService
from app.utils.security import get_current_active_user, get_product_owner_or_admin


# Create router with /product-intelligence/products prefix
router = APIRouter(
    prefix="/product-intelligence/products",
    tags=["Product Intelligence - Products"]
)


# ============================================================================
# Request/Response Schemas
# ============================================================================

class ProductCreateRequest(BaseModel):
    """Schema for creating a new product (without analysis)."""
    product_name: str = Field(..., min_length=1, max_length=255)
    product_description: str = Field(..., min_length=10)
    source_type: str = Field(default="text", pattern="^(text|document|url)$")
    source_data: Optional[dict] = None


class ProductAnalyzeRequest(BaseModel):
    """Schema for analyzing a product (Stage 1)."""
    product_description: str = Field(..., min_length=10)
    source_type: str = Field(..., pattern="^(text|document|url)$")
    source_data: Optional[dict] = None


class ProductUpdateRequest(BaseModel):
    """Schema for updating a product."""
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    product_description: Optional[str] = Field(None, min_length=10)


class ProductResponse(BaseModel):
    """Schema for returning product information."""
    id: int
    product_name: str
    product_description: str
    product_category: Optional[str]
    structured_product_data: Optional[dict]
    product_source_type: str
    product_source_data: Optional[dict]
    analysis_version: int
    last_analyzed_at: Optional[datetime]
    analysis_count: int
    created_by_user_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Product CRUD Endpoints
# ============================================================================

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    request: ProductCreateRequest,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new product WITHOUT automatic analysis (Stage 0).

    Requires: PRODUCT_OWNER or ADMIN role.

    Products are created as team resources. The creator gets implicit ADMIN access.
    Other users can be granted VIEW/EDIT/ADMIN permissions separately.

    After creation, use POST /products/{id}/analyze to analyze the product.

    Returns:
        Created product with analysis_version=0 (not yet analyzed)

    Raises:
        403: If user is not a Product Owner or Admin
        400: If product name already exists
    """
    service = ProductService(db)

    try:
        product = service.create_product(
            product_name=request.product_name,
            product_description=request.product_description,
            created_by_user_id=current_user.id,
            source_type=request.source_type,
            source_data=request.source_data
        )
        return product
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{product_id}/analyze", response_model=dict)
def analyze_product(
    product_id: int,
    request: ProductAnalyzeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    req: Request = None
):
    """
    Analyze a product with AI (Stage 1 - Independent Operation).

    This can be called multiple times to re-analyze a product as it evolves.
    Each analysis is versioned and stored in analysis history.

    Requires EDIT permission on the product.

    Returns:
        Analyzed product structure including:
        - product_name (AI-refined)
        - product_category
        - core_features
        - target_users
        - value_propositions
        - competitor_search_keywords

    Raises:
        403: If user lacks EDIT permission
        404: If product not found
    """
    service = ProductService(db)

    try:
        analyzed_structure = service.analyze_product(
            product_id=product_id,
            user_id=current_user.id,
            product_description=request.product_description,
            source_type=request.source_type,
            source_data=request.source_data,
            llm_service=llm_service
        )

        # Generate and store product embeddings after analysis completes
        if req and hasattr(req.app.state, 'embedding_model'):
            try:
                # Get the product description that was analyzed
                product_text = request.product_description

                print(f"[API] Generating embedding for product {product_id}...")

                # Check if text is large enough to require chunking
                if len(product_text) > 16000:  # ~4000 tokens
                    print(f"[API] Text is large ({len(product_text)} chars), chunking...")
                    # Simple chunking: split into ~12K char chunks with overlap
                    chunk_size = 12000
                    overlap = 1000
                    chunks = []

                    for i in range(0, len(product_text), chunk_size - overlap):
                        chunk = product_text[i:i + chunk_size]
                        if chunk.strip():
                            chunks.append(chunk)

                    print(f"[API] Created {len(chunks)} chunks")

                    # Generate embedding for each chunk
                    for i, chunk in enumerate(chunks):
                        embedding = req.app.state.embedding_model.encode(
                            chunk,
                            show_progress_bar=False
                        )
                        VectorService.store_product_embedding(
                            db,
                            product_id,
                            embedding.tolist(),
                            chunk_index=i,
                            chunk_text=chunk[:500]  # Store first 500 chars as preview
                        )

                    print(f"[API] ✓ Stored {len(chunks)} chunk embeddings for product {product_id}")
                else:
                    # Single embedding for entire product
                    embedding = req.app.state.embedding_model.encode(
                        product_text,
                        show_progress_bar=False
                    )
                    VectorService.store_product_embedding(
                        db,
                        product_id,
                        embedding.tolist(),
                        chunk_index=0,
                        chunk_text=product_text[:500]  # Store first 500 chars as preview
                    )
                    print(f"[API] ✓ Stored single embedding for product {product_id}")

                db.commit()
            except Exception as e:
                print(f"[API] Warning: Failed to generate product embedding: {e}")
                # Don't fail the request if embedding generation fails
                db.rollback()

        return {
            "product_id": product_id,
            "analysis_version": analyzed_structure.get("version", "latest"),
            "analyzed_structure": analyzed_structure
        }
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("", response_model=List[ProductResponse])
def list_products(
    permission_level: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all products accessible to the current user.

    Note: This endpoint is accessible to all authenticated users (including VOTER role)
    so they can see product names in dropdown for idea submission. However, the list
    returned is filtered based on role and permissions (see permission_service.py).

    Returns products based on:
    - User's role (VOTER sees all product names, PRODUCT_OWNER sees only their products, ADMIN sees all)
    - User's default_product_access mode (SINGLE_USER vs TEAM_WIDE)
    - Explicit product permission grants

    Args:
        permission_level: Filter by minimum permission level (view, edit, admin)

    Returns:
        List of products the user can access
    """
    service = ProductService(db)

    # Convert string to enum if provided
    perm_level = None
    if permission_level:
        try:
            perm_level = ProductPermissionLevel(permission_level.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission level. Must be: view, edit, or admin"
            )

    products = service.list_products(
        user_id=current_user.id,
        permission_level=perm_level
    )

    return products


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Get a product by ID (detail view).

    Requires: PRODUCT_OWNER or ADMIN role + VIEW permission on the product.

    Returns:
        Product details

    Raises:
        403: If user is not a Product Owner/Admin or lacks VIEW permission
        404: If product not found
    """
    service = ProductService(db)
    product = service.get_product(product_id, current_user.id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or you don't have permission to view it"
        )

    return product


@router.get("/{product_id}/analysis-history", response_model=List[dict])
def get_analysis_history(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get analysis history for a product.

    Shows all past analyses, allowing you to see how the product
    analysis has evolved over time.

    Requires VIEW permission on the product.

    Returns:
        List of analysis history records (newest first)

    Raises:
        403: If user lacks VIEW permission
        404: If product not found
    """
    service = ProductService(db)

    try:
        history = service.get_analysis_history(product_id, current_user.id)
        return [
            {
                "id": h.id,
                "analysis_version": h.analysis_version,
                "analyzed_by_user_id": h.analyzed_by_user_id,
                "product_description": h.product_description,
                "product_source_type": h.product_source_type,
                "product_source_data": h.product_source_data,
                "analyzed_structure": h.analyzed_structure,
                "tokens_used": h.tokens_used,
                "created_at": h.created_at.isoformat() + 'Z' if h.created_at else None
            }
            for h in history
        ]
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{product_id}/search")
def search_product_content(
    product_id: int,
    q: str = Query(..., min_length=10, description="Search query (minimum 10 characters)"),
    threshold: float = Query(0.6, ge=0.0, le=1.0, description="Similarity threshold (0-1, higher = more similar)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    req: Request = None
):
    """
    Semantic search within product documentation.

    Uses vector similarity search to find relevant content in the product's
    documentation. This is useful for:
    - Checking if a user idea is already implemented in the product
    - Finding relevant product sections for specific features
    - General product knowledge search

    Requires VIEW permission on the product.

    Args:
        product_id: Product ID to search within
        q: Search query (minimum 10 characters for meaningful results)
        threshold: Similarity threshold (0-1, default 0.6). Higher values return only closer matches.

    Returns:
        List of matching content chunks with similarity scores

    Raises:
        400: If query is too short or embedding model unavailable
        403: If user lacks VIEW permission
        404: If product not found or has no embeddings
    """
    # Check if embedding model is available
    if not req or not hasattr(req.app.state, 'embedding_model'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedding model not available. Semantic search is disabled."
        )

    # Check permission
    service = ProductService(db)
    product = service.get_product(product_id, current_user.id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or you don't have permission to view it"
        )

    try:
        # Generate query embedding
        query_embedding = req.app.state.embedding_model.encode(
            q,
            show_progress_bar=False
        )

        # Search product chunks
        results = VectorService.find_similar_in_product(
            db,
            query_embedding.tolist(),
            product_id,
            threshold=threshold
        )

        if not results:
            return {
                "product_id": product_id,
                "query": q,
                "threshold": threshold,
                "matches": [],
                "message": "No matches found. Try lowering the threshold or rephrasing your query."
            }

        # Convert distance to similarity score (distance = 2 * (1 - similarity))
        # So similarity = 1 - (distance / 2)
        matches = [
            {
                "text": text,
                "similarity_score": 1 - (distance / 2),
                "distance": distance
            }
            for text, distance in results
        ]

        return {
            "product_id": product_id,
            "query": q,
            "threshold": threshold,
            "matches": matches
        }

    except Exception as e:
        print(f"[API] Error during product search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/{product_id}/source-status")
def check_product_source_status(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check if product sources have changed since last analysis.

    Returns source change status to detect when product information
    is stale and requires re-analysis before starting new workflows.

    Requires VIEW permission on the product.

    Args:
        product_id: Product ID

    Returns:
        dict with:
        - sources_changed: Boolean indicating if sources have changed
        - last_analyzed_at: When product was last analyzed
        - analysis_version: Current analysis version

    Raises:
        403: If user lacks VIEW permission
        404: If product not found
    """
    service = ProductService(db)
    product = service.get_product(product_id, current_user.id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or you don't have permission to view it"
        )

    # Calculate current source hash
    current_hash = service._calculate_source_hash(
        product_description=product.product_description,
        source_type=product.product_source_type,
        source_data=product.product_source_data
    )

    # Compare to stored hash
    sources_changed = (
        product.last_source_hash is not None and
        current_hash != product.last_source_hash
    )

    return {
        "sources_changed": sources_changed,
        "last_analyzed_at": product.last_analyzed_at.isoformat() if product.last_analyzed_at else None,
        "analysis_version": product.analysis_version
    }


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    request: ProductUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update product information.

    This does NOT trigger re-analysis. Use POST /products/{id}/analyze
    to re-analyze after making changes.

    Requires EDIT permission on the product.

    Returns:
        Updated product

    Raises:
        400: If validation fails (e.g., duplicate name)
        403: If user lacks EDIT permission
        404: If product not found
    """
    service = ProductService(db)

    try:
        product = service.update_product(
            product_id=product_id,
            user_id=current_user.id,
            product_name=request.product_name,
            product_description=request.product_description
        )
        return product
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a product (hard delete).

    This will cascade delete all related data:
    - Analysis sessions
    - Competitors
    - Features
    - Generated ideas
    - Permissions

    Requires ADMIN permission on the product.

    Raises:
        403: If user lacks ADMIN permission
        404: If product not found
    """
    service = ProductService(db)

    try:
        success = service.delete_product(product_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        return None
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


# ============================================================================
# Document Upload & URL Fetching Endpoints
# ============================================================================

@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload and parse a document (PDF, DOCX, TXT, MD).

    Supported formats: .pdf, .docx, .txt, .md
    Maximum size: 50MB

    The file is saved to temporary storage and parsed to extract text.
    The extracted text is returned immediately for frontend preview.
    Files are moved to permanent storage when the product is created/analyzed.

    Requires: Any authenticated user

    Returns:
        {
            'file_id': str (UUID for tracking),
            'filename': str,
            'file_type': str (extension),
            'extracted_text': str,
            'size_mb': float,
            'token_estimate': int
        }

    Raises:
        400: If file validation fails or parsing fails
        500: If unexpected error occurs
    """
    parsing_service = DocumentParsingService()

    # Validate file
    validation = parsing_service.validate_file(file)
    if not validation['valid']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation['error']
        )

    # Generate unique file ID
    file_id = str(uuid.uuid4())
    file_ext = validation['file_type']
    safe_filename = f"{file_id}_{file.filename}"

    # Create temp directory if it doesn't exist
    temp_dir = Path("uploads/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Save file to temp location
    temp_path = temp_dir / safe_filename
    try:
        with open(temp_path, 'wb') as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    # Parse document based on type
    try:
        if file_ext == '.pdf':
            extracted_text = parsing_service.parse_pdf(str(temp_path))
        elif file_ext == '.docx':
            extracted_text = parsing_service.parse_docx(str(temp_path))
        elif file_ext in ['.txt', '.md']:
            extracted_text = parsing_service.parse_text_file(str(temp_path))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}"
            )
    except Exception as e:
        # Clean up temp file on parse failure
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse document: {str(e)}"
        )

    # Calculate token estimate
    token_estimate = parsing_service.count_tokens_estimate(extracted_text)

    return {
        'file_id': file_id,
        'filename': file.filename,
        'file_type': file_ext,
        'extracted_text': extracted_text,
        'size_mb': round(validation['size_mb'], 2),
        'token_estimate': token_estimate
    }


@router.post("/fetch-url")
async def fetch_url(
    url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user)
):
    """
    Fetch and extract content from a URL.

    Fetches HTML content and extracts main text using BeautifulSoup.
    Converts HTML to clean markdown-style text for better readability.

    Security features:
    - SSRF prevention (blocks internal IPs)
    - Timeout: 10 seconds
    - Max redirects: 3
    - Only allows http/https protocols

    Requires: Any authenticated user

    Returns:
        {
            'url': str (final URL after redirects),
            'title': str (page title),
            'extracted_text': str,
            'fetch_timestamp': str (ISO format),
            'token_estimate': int
        }

    Raises:
        400: If URL is invalid, blocked, or fetch fails
        500: If unexpected error occurs
    """
    parsing_service = DocumentParsingService()

    try:
        result = parsing_service.fetch_url_content(url)

        # Add token estimate
        result['token_estimate'] = parsing_service.count_tokens_estimate(
            result['extracted_text']
        )

        return result
    except ValueError as e:
        # Validation errors (invalid URL, blocked IP, etc.)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Fetch errors (timeout, connection failed, etc.)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
