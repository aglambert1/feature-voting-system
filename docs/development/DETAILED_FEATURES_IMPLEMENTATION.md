# Detailed Features Implementation

## Overview

This document describes the implementation of two-level feature extraction in the product analysis system. The system now extracts both **strategic core features** and **tactical detailed features** to provide comprehensive product analysis that matches the granularity of competitor feature extraction.

## Problem Statement

Previously, there was a significant discrepancy in feature extraction detail levels:

- **Product Analysis**: Extracted 5-7 "core features" at a strategic level
- **Competitor Feature Extraction**: Extracted 10-25 "distinct features" at a granular level

This made comparisons difficult because competitor products always appeared to have more features due to the difference in extraction granularity.

## Solution

### Two-Level Feature Extraction

The product analyzer now extracts features at two levels:

1. **Core Features (5-7)**: High-level strategic capabilities that define the product
   - Stored in `analyzed_structure.core_features` (JSON field)
   - Used for product summaries and high-level comparisons
   - Example: "Contact management", "Sales pipeline tracking", "Email integration"

2. **Detailed Features (10-25)**: Granular, verifiable capabilities
   - Stored in dedicated `product_features` database table
   - Used for detailed comparisons with competitors and ideas
   - Example: "Custom fields", "Drag-and-drop interface", "Gmail integration"

### Database Schema

#### New Table: `product_features`

```sql
CREATE TABLE product_features (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    analysis_history_id INTEGER NOT NULL,
    analysis_version INTEGER NOT NULL,

    -- Feature details
    feature_name VARCHAR(255) NOT NULL,
    feature_description TEXT,
    feature_category VARCHAR(100),
    extraction_confidence DECIMAL(3,2),
    source_reference TEXT,

    -- Metadata
    status VARCHAR(50) DEFAULT 'active',
    created_at DATETIME,
    updated_at DATETIME,

    FOREIGN KEY (product_id) REFERENCES ci_products(id),
    FOREIGN KEY (analysis_history_id) REFERENCES product_analysis_history(id)
)
```

#### Updated Model: `ProductAnalysisHistory`

Added relationship to detailed features:

```python
detailed_features = relationship("ProductFeature",
                                back_populates="analysis_history",
                                cascade="all, delete-orphan")
```

### Agent Updates

#### Updated Schema: `ProductAnalysisOutput`

```python
class DetailedProductFeature(BaseModel):
    name: str = Field(..., max_length=255, description="Feature name (2-5 words)")
    description: str = Field(..., description="Feature description (1-2 sentences)")
    category: str = Field(..., description="Feature category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    source_reference: str = Field(None, description="Where this feature was found")

class ProductAnalysisOutput(BaseModel):
    product_name: str
    product_category: str
    core_features: list[str] = Field(..., min_length=3, max_length=10,
        description="5-7 strategic core features that define the product")
    detailed_features: list[DetailedProductFeature] = Field(..., min_length=5, max_length=30,
        description="10-25 detailed tactical features extracted from the product")
    target_users: str
    value_propositions: list[str]
    competitor_search_keywords: list[str]
```

#### Updated Prompt

The product analyzer prompt now explicitly requests two levels of features:

1. **core_features**: High-level strategic capabilities (5-7 items)
   - "What would you put on a homepage banner"

2. **detailed_features**: Comprehensive list of all identifiable features (10-25 items)
   - Granular, verifiable capabilities
   - Each with name, description, category, confidence, and source reference

### Service Updates

#### ProductService.analyze_product()

After running the AI analysis, the service now:

1. Stores the analysis in `ProductAnalysisHistory` (includes both core and detailed features in JSON)
2. Extracts `detailed_features` from the analysis result
3. Creates individual `ProductFeature` records for each detailed feature
4. Links them to the analysis history via `analysis_history_id` and `analysis_version`

```python
# Store detailed features
detailed_features_data = analyzed_structure.get('detailed_features', [])
if detailed_features_data:
    for feature_data in detailed_features_data:
        product_feature = ProductFeature(
            product_id=product_id,
            analysis_history_id=history.id,
            analysis_version=new_version,
            feature_name=feature_data.get('name'),
            feature_description=feature_data.get('description'),
            feature_category=feature_data.get('category'),
            extraction_confidence=feature_data.get('confidence'),
            source_reference=feature_data.get('source_reference'),
            status='active'
        )
        self.db.add(product_feature)
```

### API Endpoints

#### New Endpoint: `GET /product-intelligence/products/{product_id}/detailed-features`

Retrieves detailed features for a specific product and analysis version:

**Query Parameters:**
- `analysis_version` (optional): Specific version to retrieve (default: latest)

**Response:**
```json
[
  {
    "id": 1,
    "feature_name": "Contact management",
    "feature_description": "Centralized system for storing and managing customer information",
    "feature_category": "Core Functionality",
    "extraction_confidence": 0.95,
    "source_reference": "Main feature in description",
    "created_at": "2025-12-21T..."
  },
  ...
]
```

**Features:**
- Requires VIEW permission on the product
- Returns features ordered by category and name
- Only returns active features
- Defaults to latest analysis version if not specified

## Usage

### 1. Create and Analyze a Product

```python
# Create product
POST /product-intelligence/products
{
    "product_name": "My CRM",
    "product_description": "Full product description...",
    "source_type": "text"
}

# Analyze product (extracts both core and detailed features)
POST /product-intelligence/products/{product_id}/analyze
{
    "product_description": "Full product description...",
    "source_type": "text"
}
```

### 2. View Product Summary (Core Features)

The core features are available in the product's `structured_product_data`:

```python
GET /product-intelligence/products/{product_id}

Response:
{
    "id": 1,
    "product_name": "My CRM",
    "structured_product_data": {
        "product_name": "My CRM",
        "product_category": "CRM Software",
        "core_features": [
            "Contact management",
            "Sales pipeline tracking",
            "Email integration",
            ...
        ],
        "detailed_features": [...],  // Full list also stored here
        ...
    }
}
```

### 3. View Detailed Features

Retrieve the detailed feature list for granular analysis:

```python
GET /product-intelligence/products/{product_id}/detailed-features

Response: [
    {
        "feature_name": "Contact management",
        "feature_description": "Centralized database for contacts",
        "feature_category": "Core Functionality",
        ...
    },
    {
        "feature_name": "Custom fields",
        "feature_description": "Add custom data fields to records",
        "feature_category": "Data Management",
        ...
    },
    ...
]
```

## Benefits

1. **Consistent Granularity**: Product features and competitor features are now extracted at the same level of detail
2. **Dual Purpose**: Core features provide strategic overview, detailed features enable granular comparison
3. **Structured Storage**: Detailed features are stored in a relational table, enabling:
   - Efficient querying and filtering
   - Feature-level comparisons
   - Historical tracking across analysis versions
4. **Future Use Cases**:
   - Compare product features with competitor features
   - Compare product features with user ideas
   - Track feature evolution over time
   - Generate insights based on feature gaps

## Testing

Run the comprehensive test:

```bash
./venv/bin/python test_detailed_features.py
```

The test validates:
- Product creation
- Product analysis (extracting both core and detailed features)
- Retrieval of detailed features via API
- Correct number of features (10-25)
- Proper categorization
- All required fields present

## Example Output

```
Test CRM System Analysis:
  Core Features (7):
    1. Contact management
    2. Sales pipeline tracking
    3. Email integration
    4. Mobile applications
    5. Reporting and analytics
    6. Team collaboration
    7. Custom workflows

  Detailed Features (22):
    - Contact management (Core Functionality)
    - Custom fields (Data Management)
    - Sales pipeline tracking (Core Functionality)
    - Drag-and-drop interface (User Experience)
    - Gmail integration (Integration)
    - Outlook integration (Integration)
    - Automated follow-up (Automation)
    - Activity logging (Core Functionality)
    - Reporting dashboard (Analytics)
    ... and 13 more

  Features by Category:
    - Analytics: 2 features
    - Automation: 2 features
    - Collaboration: 1 features
    - Core Functionality: 3 features
    - Data Management: 4 features
    - Integration: 4 features
    - Mobile Access: 2 features
    - Productivity: 1 features
    - Security: 1 features
    - User Experience: 2 features
```

## Migration

The database migration script is provided:

```bash
./venv/bin/python migrate_add_product_features.py
```

This creates the `product_features` table without affecting existing data.

## Files Modified

1. **Backend:**
   - `app/agents/product_analyzer.py` - Updated schema and prompt
   - `app/models/competitor_intelligence.py` - Added ProductFeature model
   - `app/services/product_service.py` - Store detailed features
   - `app/api/products.py` - Added detailed features endpoint
   - `migrate_add_product_features.py` - Database migration script

2. **Testing:**
   - `test_detailed_features.py` - Comprehensive test suite

3. **Documentation:**
   - `docs/DETAILED_FEATURES_IMPLEMENTATION.md` - This document
