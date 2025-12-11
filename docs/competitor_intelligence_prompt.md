# Build Multi-Agent Competitor Intelligence System

## Overview
Build a sophisticated, AI-powered competitor intelligence feature with a multi-agent architecture that guides users through discovering competitors, analyzing their features, and converting insights into votable ideas with full traceability.

## Technology Stack (from ARCHITECTURE.md)
- **Backend**: FastAPI (Python 3.11+) with PostgreSQL + pgvector
- **Frontend**: React 18+ with Vite, TailwindCSS, React Router v6
- **AI**: Anthropic Claude API for multi-agent coordination
- **Background Jobs**: Celery for parallel processing
- **Existing Services**: LLMService, SimilarityService already implemented

## Multi-Agent Workflow Architecture

### Workflow Stages with User Interaction Points

```
Stage 1: Product Definition
├─→ User Input: Text/Document/URL describing their product
├─→ Agent: Product Analyzer (structures product description)
└─→ User Review: Confirm understanding of product

Stage 2: Competitor Discovery  
├─→ Agent: Competitor Research Agent (web search for competitors)
├─→ AI Output: List of 10-15 potential competitors with summaries
└─→ User Selection: Choose competitors + add custom ones

Stage 3: Parallel Feature Extraction (Celery background jobs)
├─→ Multiple Feature Extraction Agents (one per competitor, parallel)
├─→ Each agent researches competitor and extracts features
├─→ AI Output: Competitor features with descriptions
└─→ User Selection: Choose features to include + request details

Stage 4: Idea Generation
├─→ Agent: Idea Structuring Agent (converts features to ideas)
├─→ AI Output: Structured ideas (What/Why/UseCase)
└─→ User Review: Edit ideas before submission

Stage 5: Database Integration
└─→ Store ideas with full traceability to source
```

## Database Schema

### New Tables

```sql
-- Products are the primary organizing entity
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by_user_id UUID NOT NULL REFERENCES users(id),
    product_name VARCHAR(255) NOT NULL,
    product_description TEXT NOT NULL,
    product_category VARCHAR(100), -- AI-determined category
    structured_product_data JSONB, -- AI's structured understanding (core features, target users, etc.)
    last_analyzed_at TIMESTAMP,
    analysis_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(created_by_user_id, product_name) -- Same user can't create duplicate product names
);

-- Analysis sessions are linked to products for comparative tracking
CREATE TABLE competitor_analysis_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    session_name VARCHAR(255), -- Optional user-provided name, e.g., "Q4 2024 Analysis"
    analysis_type VARCHAR(50) NOT NULL DEFAULT 'full', -- 'full' or 'differential'
    comparison_to_session_id UUID REFERENCES competitor_analysis_sessions(id), -- For differential analysis
    product_source_type VARCHAR(50) NOT NULL, -- 'text', 'document', 'url'
    product_source_data JSONB, -- stores file path or URL for this specific session
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- 'active', 'completed', 'abandoned'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Competitors are tracked at product level across sessions
CREATE TABLE product_competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    competitor_name VARCHAR(255) NOT NULL,
    competitor_url VARCHAR(500),
    first_discovered_session_id UUID NOT NULL REFERENCES competitor_analysis_sessions(id),
    last_seen_session_id UUID REFERENCES competitor_analysis_sessions(id),
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- 'active', 'disappeared', 'monitoring'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, competitor_name)
);

-- Session-specific competitor data (discoveries and selections per analysis)
CREATE TABLE session_competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES competitor_analysis_sessions(id) ON DELETE CASCADE,
    product_competitor_id UUID REFERENCES product_competitors(id), -- NULL if new discovery
    competitor_name VARCHAR(255) NOT NULL,
    competitor_url VARCHAR(500),
    ai_summary TEXT, -- AI-generated summary of competitor
    discovery_source VARCHAR(50) NOT NULL, -- 'ai_search', 'user_added', 'previous_analysis'
    is_new_discovery BOOLEAN DEFAULT FALSE, -- New in this session vs previous
    selected_by_user BOOLEAN DEFAULT FALSE,
    discovery_rank INTEGER, -- order from AI discovery
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Features tracked at product-competitor level across sessions
CREATE TABLE product_competitor_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_competitor_id UUID NOT NULL REFERENCES product_competitors(id) ON DELETE CASCADE,
    feature_name VARCHAR(255) NOT NULL,
    feature_description TEXT,
    feature_category VARCHAR(100),
    first_discovered_session_id UUID NOT NULL REFERENCES competitor_analysis_sessions(id),
    last_seen_session_id UUID REFERENCES competitor_analysis_sessions(id),
    status VARCHAR(50) NOT NULL DEFAULT 'active', -- 'active', 'removed', 'changed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session-specific feature extractions with change detection
CREATE TABLE competitor_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_competitor_id UUID NOT NULL REFERENCES session_competitors(id) ON DELETE CASCADE,
    product_feature_id UUID REFERENCES product_competitor_features(id), -- Links to historical feature
    feature_name VARCHAR(255) NOT NULL,
    feature_description TEXT,
    feature_category VARCHAR(100), -- AI-determined category
    extraction_confidence DECIMAL(3,2), -- 0.00 to 1.00
    source_url VARCHAR(500), -- specific page where found
    raw_context TEXT, -- raw text where feature was found
    change_type VARCHAR(50), -- 'new', 'unchanged', 'modified', 'removed'
    change_description TEXT, -- AI description of what changed
    comparison_to_feature_id UUID REFERENCES competitor_features(id), -- Previous version
    selected_by_user BOOLEAN DEFAULT FALSE,
    detail_requested BOOLEAN DEFAULT FALSE,
    expanded_description TEXT, -- filled if user requests more details
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated ideas from competitor features
CREATE TABLE competitor_generated_ideas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id UUID NOT NULL REFERENCES competitor_features(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES competitor_analysis_sessions(id),
    idea_what TEXT NOT NULL, -- structured by AI
    idea_why TEXT NOT NULL,
    idea_use_case TEXT NOT NULL,
    user_edited BOOLEAN DEFAULT FALSE,
    user_approved BOOLEAN DEFAULT FALSE,
    submitted_to_ideas BOOLEAN DEFAULT FALSE,
    final_idea_id UUID REFERENCES ideas(id), -- links to main ideas table
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited_at TIMESTAMP
);

-- Agent execution logs for debugging and monitoring
CREATE TABLE agent_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES competitor_analysis_sessions(id),
    agent_name VARCHAR(100) NOT NULL, -- 'product_analyzer', 'competitor_researcher', etc.
    stage VARCHAR(50) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    llm_tokens_used INTEGER,
    execution_time_ms INTEGER,
    status VARCHAR(50) NOT NULL, -- 'success', 'error', 'partial'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_user ON products(created_by_user_id);
CREATE INDEX idx_products_name ON products(product_name);
CREATE INDEX idx_sessions_product ON competitor_analysis_sessions(product_id);
CREATE INDEX idx_sessions_user ON competitor_analysis_sessions(user_id);
CREATE INDEX idx_sessions_status ON competitor_analysis_sessions(status);
CREATE INDEX idx_product_competitors_product ON product_competitors(product_id);
CREATE INDEX idx_product_competitors_status ON product_competitors(status);
CREATE INDEX idx_session_competitors_session ON session_competitors(session_id);
CREATE INDEX idx_session_competitors_product_comp ON session_competitors(product_competitor_id);
CREATE INDEX idx_session_competitors_new ON session_competitors(is_new_discovery);
CREATE INDEX idx_product_features_competitor ON product_competitor_features(product_competitor_id);
CREATE INDEX idx_product_features_status ON product_competitor_features(status);
CREATE INDEX idx_features_session_competitor ON competitor_features(session_competitor_id);
CREATE INDEX idx_features_product_feature ON competitor_features(product_feature_id);
CREATE INDEX idx_features_change_type ON competitor_features(change_type);
CREATE INDEX idx_features_selected ON competitor_features(selected_by_user);
CREATE INDEX idx_ideas_session ON competitor_generated_ideas(session_id);
CREATE INDEX idx_ideas_submitted ON competitor_generated_ideas(submitted_to_ideas);
CREATE INDEX idx_agent_logs_session ON agent_execution_logs(session_id);
```

## Backend Implementation

### 1. Multi-Agent Service (`app/services/competitor_intelligence_service.py`)

Create a comprehensive service that orchestrates all AI agents:

```python
# Key methods to implement:

class CompetitorIntelligenceService:
    """Orchestrates multi-agent competitor intelligence workflow"""
    
    async def create_or_get_product(
        self, 
        user_id: UUID, 
        product_input: ProductInput
    ) -> Tuple[Product, bool]:
        """
        Create new product or return existing one
        Returns: (Product, is_new: bool)
        Uses Product Analyzer Agent to structure product description
        """
    
    async def list_user_products(self, user_id: UUID) -> List[ProductSummary]:
        """
        Get all products for user with summary stats
        Returns: List of products with analysis_count, last_analyzed_at, etc.
        """
    
    async def get_product_history(self, product_id: UUID) -> ProductHistory:
        """
        Get complete analysis history for a product
        Returns: All sessions, competitor evolution, feature changes over time
        """
    
    async def create_session(
        self, 
        user_id: UUID, 
        product_id: UUID,
        session_name: Optional[str] = None,
        analysis_type: str = 'full'
    ) -> Session:
        """
        Stage 1: Initialize new analysis session for existing product
        If previous sessions exist, prepare for differential analysis
        """
    
    async def discover_competitors(
        self, 
        session_id: UUID,
        compare_to_previous: bool = True
    ) -> CompetitorDiscoveryResult:
        """
        Stage 2: AI web research to find competitors
        If compare_to_previous=True and previous sessions exist:
          - Load competitors from previous analysis
          - Run new discovery
          - Compare and flag: new, continuing, disappeared
          - Use Differential Analysis Agent
        Returns: Competitors with change indicators
        """
        
    async def confirm_competitors(
        self, 
        session_id: UUID, 
        selected_ids: List[UUID],
        custom_competitors: List[Dict]
    ) -> bool:
        """
        User confirms competitor selection
        Creates session_competitors and links to product_competitors
        """
        
    async def extract_features_parallel(
        self, 
        session_id: UUID,
        compare_to_previous: bool = True
    ) -> Dict[UUID, FeatureExtractionResult]:
        """
        Stage 3: Parallel feature extraction for all selected competitors
        If compare_to_previous=True:
          - Load features from previous analysis for same competitors
          - Pass to Feature Extraction Agent for comparison
          - Agent identifies: new, unchanged, modified, removed features
          - Returns features with change_type indicators
        Create Celery tasks for each competitor
        """
        
    async def get_feature_details(self, feature_id: UUID) -> Feature:
        """Expand details for a specific feature on user request"""
        # Use Feature Detail Agent
        
    async def get_change_summary(self, session_id: UUID) -> ChangeSummary:
        """
        Generate summary of changes detected in this analysis
        Returns: 
          - New competitors count
          - Disappeared competitors count
          - New features count
          - Modified features count
          - Removed features count
        """
    
    async def generate_ideas(
        self, 
        session_id: UUID, 
        selected_feature_ids: List[UUID],
        only_new_features: bool = False
    ) -> List[GeneratedIdea]:
        """
        Stage 4: Convert features to structured ideas
        If only_new_features=True, filter to change_type='new' or 'modified'
        Use Idea Structuring Agent
        """
        
    async def finalize_ideas(
        self, 
        session_id: UUID, 
        idea_edits: List[Dict]
    ) -> List[UUID]:
        """
        Stage 5: Store approved ideas in main ideas table
        Insert with full traceability including change detection metadata
        # Generate embeddings for similarity search
        # Link back to competitor_generated_ideas
```

### 2. AI Agent Definitions (`app/agents/`)

Create separate agent modules, each with specific prompts and behaviors:

**`app/agents/product_analyzer.py`**
- Analyzes user's product description (text/doc/URL)
- Extracts: product name, category, key features, target users, unique value props
- Structures into standardized format for competitor research

**`app/agents/competitor_researcher.py`**
- Takes structured product description
- Performs web searches for competitors
- Identifies 10-15 potential competitors
- Generates brief summary for each (2-3 sentences)
- Ranks by relevance
- Returns: name, URL, summary, relevance score

**`app/agents/differential_analysis_agent.py`** (NEW)
- Compares new competitor discovery results with previous analysis
- Identifies: new competitors, continuing competitors, disappeared competitors
- Explains changes in competitive landscape
- Takes: current discovery results + previous session competitors
- Returns: annotated competitor list with change indicators

**`app/agents/feature_extractor.py`**
- Researches single competitor in depth
- Extracts product features with descriptions
- Categorizes features (e.g., "Core Functionality", "Integrations", "Pricing")
- Assigns confidence scores
- **NEW**: If previous features provided, compares and identifies changes
- **NEW**: Detects: new features, modified features, removed features, unchanged features
- Can be run in parallel via Celery for multiple competitors

**`app/agents/feature_detail_expander.py`**
- Takes a feature and its context
- Provides expanded explanation on user request
- Includes use cases, technical details, benefits

**`app/agents/idea_structuring_agent.py`**
- Converts competitor features into anonymized ideas
- Formats into What/Why/UseCase structure
- Removes competitor-specific branding
- Maintains feature value proposition

**`app/agents/differential_analysis_agent.py`** (NEW - for comparison mode)
- Compares current analysis with previous session
- For competitors: identifies new, continuing, disappeared
- For features: identifies new, modified, unchanged, removed
- Generates change summaries and significant changes list
- Prioritizes differential insights for idea generation

**Agent Base Class Pattern:**
```python
class BaseAgent:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        
    async def execute(self, input_data: Dict) -> Dict:
        """Execute agent with logging"""
        # Log input
        # Call Claude API with agent-specific prompt
        # Parse and validate output
        # Log execution metrics
        # Return structured result
        
    def _build_prompt(self, input_data: Dict) -> str:
        """Agent-specific prompt construction"""
        raise NotImplementedError
```

### 3. API Endpoints (`app/routers/competitor_intelligence.py`)

```python
# Product Management
GET /api/competitor-intelligence/products
    Returns: { products: [{ id, name, description, analysis_count, last_analyzed_at }] }

POST /api/competitor-intelligence/products
    Body: { product_input: text/file/url, product_type: 'text'|'document'|'url' }
    Returns: { product_id, product, is_new: bool }

GET /api/competitor-intelligence/products/{product_id}
    Returns: { product, sessions: [...], competitor_evolution, feature_trends }

GET /api/competitor-intelligence/products/{product_id}/history
    Returns: Complete analysis history with timeline visualization data

# Session Management
POST /api/competitor-intelligence/products/{product_id}/sessions
    Body: { session_name?, analysis_type: 'full'|'differential' }
    Returns: { session_id, session }

GET /api/competitor-intelligence/sessions/{session_id}
    Returns: Complete session state with all stages

# Stage 2: Competitor Discovery
POST /api/competitor-intelligence/sessions/{session_id}/discover
    Query: ?compare_to_previous=true
    Returns: { 
        competitors: [{ id, name, url, summary, rank, is_new, status_change? }],
        comparison_summary?: { new: 3, continuing: 5, disappeared: 2 }
    }

POST /api/competitor-intelligence/sessions/{session_id}/competitors/confirm
    Body: { selected_ids: [uuid], custom_competitors: [...] }
    Returns: { confirmed_count }

# Stage 3: Feature Extraction
POST /api/competitor-intelligence/sessions/{session_id}/extract-features
    Query: ?compare_to_previous=true
    Triggers: Celery tasks for parallel processing
    Returns: { task_id, status: 'processing' }

GET /api/competitor-intelligence/sessions/{session_id}/extraction-status
    Returns: { 
        status, 
        completed_count, 
        total_count, 
        features_by_competitor: { 
            competitor_id: { 
                total: 25, 
                new: 5, 
                modified: 3, 
                unchanged: 15,
                removed: 2 
            } 
        }
    }

GET /api/competitor-intelligence/sessions/{session_id}/change-summary
    Returns: {
        new_competitors: 3,
        disappeared_competitors: 1,
        total_features_found: 120,
        new_features: 25,
        modified_features: 10,
        removed_features: 5,
        significant_changes: [{ competitor, change_type, description }]
    }

GET /api/competitor-intelligence/features/{feature_id}/details
    Returns: { feature with expanded_description }

# Stage 4: Idea Generation
POST /api/competitor-intelligence/sessions/{session_id}/generate-ideas
    Body: { selected_feature_ids: [uuid], only_new_features?: bool }
    Returns: { 
        generated_ideas: [{ 
            id, what, why, use_case, 
            source_feature, 
            change_type 
        }] 
    }

PATCH /api/competitor-intelligence/ideas/{idea_id}
    Body: { what?, why?, use_case? }
    Returns: { updated_idea }

# Stage 5: Finalization
POST /api/competitor-intelligence/sessions/{session_id}/finalize
    Body: { approved_idea_ids: [uuid] }
    Returns: { 
        submitted_idea_ids: [uuid], 
        links_to_main_ideas,
        traceability: [{ idea_id, competitor, feature, change_type }]
    }
```

### 4. Celery Tasks (`app/tasks/competitor_tasks.py`)

```python
@celery_app.task
def extract_competitor_features(
    competitor_id: UUID, 
    session_id: UUID,
    previous_features: Optional[List[Dict]] = None
):
    """
    Background task for feature extraction with optional comparison
    If previous_features provided, performs differential analysis
    """
    # Run Feature Extraction Agent
    # If previous_features exist, agent compares and identifies changes
    # Store results in competitor_features table with change_type
    # Update product_competitor_features table
    # Return feature count and change summary
    
@celery_app.task
def parallel_feature_extraction(
    session_id: UUID, 
    competitor_ids: List[UUID],
    compare_to_previous: bool = True
):
    """
    Coordinator task that spawns parallel extraction tasks
    If compare_to_previous, loads previous features for each competitor
    """
    # For each competitor, check if it exists in previous analysis
    # Load previous features if found
    # Create group of tasks with previous features passed in
    # Execute in parallel
    # Aggregate results with change statistics
```

## Frontend Implementation

### Component Structure

```
src/pages/CompetitorIntelligence/
├── ProductList.tsx (landing page - shows all products)
├── ProductDetail.tsx (shows history and sessions for a product)
├── CompetitorIntelligenceWizard.tsx (main session coordinator)
├── Stage1_ProductDefinition.tsx (create/select product)
├── Stage2_CompetitorDiscovery.tsx (with change indicators)
├── Stage3_FeatureExtraction.tsx (with change detection UI)
├── Stage4_IdeaGeneration.tsx (filter by change type)
├── Stage5_Review.tsx (shows traceability)
└── components/
    ├── ProductCard.tsx
    ├── ProductHistoryTimeline.tsx
    ├── SessionCard.tsx
    ├── ProductInputForm.tsx
    ├── CompetitorCard.tsx (with change badges)
    ├── CompetitorComparisonView.tsx (side-by-side comparison)
    ├── FeatureTable.tsx (with change type column)
    ├── FeatureChangeIndicator.tsx (visual badges for new/modified/removed)
    ├── ChangeSummaryCard.tsx (dashboard of changes)
    ├── IdeaEditor.tsx
    ├── ProgressIndicator.tsx
    └── AgentActivityIndicator.tsx (shows AI processing)
```

### Key Components

**0. Product List Page (`ProductList.tsx`)** (NEW LANDING PAGE)
```typescript
// Main landing page - replaces direct wizard access
// Display: Grid of product cards
// Each card shows: Product name, last analyzed date, analysis count, brief description
// Actions: 
//   - Click to view product detail/history
//   - "+ New Product Analysis" button (creates product + starts wizard)
// State: List of user's products from API
```

**0b. Product Detail Page (`ProductDetail.tsx`)** (NEW)
```typescript
// Shows complete history for a product
// Display:
//   - Product overview (name, description, category)
//   - Timeline of analysis sessions
//   - Competitor evolution chart (who appeared/disappeared over time)
//   - Feature trends (new features over time)
//   - All generated ideas from this product
// Actions:
//   - "Start New Analysis" button → launches wizard
//   - Click session to view details (read-only)
//   - "Edit Product" to update description
// Includes: ProductHistoryTimeline, CompetitorComparisonView components
```

**1. Wizard Container (`CompetitorIntelligenceWizard.tsx`)**
```typescript
// State management for multi-stage workflow
const [productId, setProductId] = useState<string | null>(null);
const [sessionId, setSessionId] = useState<string | null>(null);
const [currentStage, setCurrentStage] = useState<1|2|3|4|5>(1);
const [sessionData, setSessionData] = useState<Session | null>(null);
const [hasPreviousAnalysis, setHasPreviousAnalysis] = useState<boolean>(false);
const [compareMode, setCompareMode] = useState<boolean>(true); // Default ON if previous exists

// NEW: Check if product has previous analysis
// If yes, show option to enable/disable comparison mode
// Stage progression with validation
const canProgressToStage = (stage: number): boolean => {
  // Validate required data for each stage
};

// Visual progress stepper (1 → 2 → 3 → 4 → 5)
// If compareMode enabled, show "Comparison Mode" indicator
```

**2. Stage 1: Product Definition (Updated)**
```typescript
// Two paths:
// Path A: New Product
//   - Input modes: Text area, File upload, URL input
//   - Real-time AI analysis with loading state
//   - Display: Structured product understanding with edit capability
//   - CTA: "Find Competitors" (progresses to Stage 2)

// Path B: Existing Product (launched from ProductDetail page)
//   - Show existing product info (read-only or editable)
//   - Option: "Use existing description" or "Update product description"
//   - Show: "Previous analysis found - comparison mode enabled"
//   - Toggle: Enable/disable comparison mode
//   - CTA: "Find Competitors" (progresses to Stage 2)
```

**3. Stage 2: Competitor Discovery (Updated)**
```typescript
// Trigger AI research on mount
// Display: Grid/list of competitor cards WITH CHANGE INDICATORS
// Each card shows:
//   - Name, URL, AI summary
//   - Badge: "NEW" (green), "CONTINUING" (blue), "DISAPPEARED" (red)
//   - Status change explanation if applicable
//   - "Select" checkbox
// NEW: Change Summary Card at top
//   - "3 new competitors found"
//   - "1 competitor no longer detected"
//   - "5 continuing competitors"
// "+ Add Custom Competitor" button
// Show selected count
// CTA: "Extract Features" (progresses to Stage 3)

// AI Activity Indicator: "Comparing with previous analysis..." or "Researching competitors..."
```

**4. Stage 3: Feature Extraction (Updated)**
```typescript
// Trigger parallel extraction on mount
// Display: Progress by competitor (e.g., "3 of 5 complete")
// Real-time updates via polling or WebSocket

// NEW: Change Summary Dashboard at top (if comparison mode)
//   - "25 new features found"
//   - "10 features modified"
//   - "5 features removed"
//   - "80 features unchanged"

// Expandable sections per competitor
// Feature table with columns:
//   - Feature Name
//   - Description (truncated)
//   - Category
//   - Change Type (NEW column) - with color-coded badges:
//     * "NEW" (green)
//     * "MODIFIED" (orange) - with hover showing what changed
//     * "REMOVED" (red strikethrough)
//     * "UNCHANGED" (gray) - hidden by default with "Show all" toggle
//   - Select checkbox (disabled for REMOVED features)
// "Request Details" button on each feature
// Filter options: "Show only changes" toggle (default ON)
// CTA: "Generate Ideas" (progresses to Stage 4)

// AI Activity: Multiple agent indicators showing parallel work
// If comparison mode: "Comparing with [Date] analysis..."
```

**5. Stage 4: Idea Generation (Updated)**
```typescript
// NEW: Option at top
//   - Checkbox: "Only generate ideas for new/modified features" (default checked if comparison mode)
//   - This filters selected_feature_ids to only change_type='new' or 'modified'

// Trigger idea generation on mount
// Display: List of generated ideas with edit capability
// Each idea shows:
//   - What (editable)
//   - Why (editable)
//   - Use Case (editable)
//   - Source: "Based on [Feature X] from [Competitor Y]"
//   - NEW: Change badge if from new/modified feature
//   - "Approve" checkbox
// CTA: "Submit Ideas" (progresses to Stage 5)
```

**6. Stage 5: Review & Finalize (Updated)**
```typescript
// Summary view of entire session
// Show: Product analyzed, competitors researched, features found, ideas created

// NEW: If comparison mode, show Change Summary:
//   - New competitors discovered: X
//   - New features found: Y
//   - Modified features: Z
//   - Ideas generated from changes: N

// List of approved ideas ready for submission
// Each idea shows full traceability:
//   - Idea content (What/Why/UseCase)
//   - Source: Competitor name → Feature name
//   - Change type (if applicable): "NEW", "MODIFIED", or blank
//   - Link to original feature for reference

// Final CTA: "Submit to Voting System"
// Success: Show links to submitted ideas in main system
// Display: "X ideas submitted with full traceability"
```

### UI/UX Considerations

**AI Activity Indicators:**
- Animated icons showing agent activity
- "Agent: [Name] is [action]..." messages
- Progress bars for long-running operations
- Estimated time remaining
- NEW: "Comparison mode active - analyzing changes from [Date]"

**Data Visualization:**
- Competitor comparison matrix (side-by-side view of old vs new)
- Feature category breakdown (pie/bar chart)
- Session timeline showing stages completed
- NEW: Change trends over time (line chart showing feature/competitor evolution)
- NEW: Change heatmap (which competitors have most changes)

**Change Indicators:**
- Color-coded badges: Green (NEW), Orange (MODIFIED), Red (REMOVED), Gray (UNCHANGED)
- Visual timeline showing when competitors/features appeared/disappeared
- Diff view for modified features (show before/after)
- "What changed?" explanations in plain language

**Product-Centric Navigation:**
- Breadcrumb: Products → [Product Name] → Session [Date]
- Easy navigation back to product history
- "Compare with previous analysis" toggle throughout workflow

**Error Handling:**
- Graceful failures with retry options
- Partial success handling (e.g., 4 of 5 competitors succeeded)
- Save draft capability to resume later

**Responsive Design:**
- Mobile-friendly wizard navigation
- Touch-optimized selection interfaces
- Collapsible sections for mobile

## AI Agent Implementation Details

### Agent Prompt Engineering

**Product Analyzer Agent Prompt:**
```
You are a Product Analyzer agent. Your role is to understand a product description and structure it for competitive analysis.

Input: [Product description as text, document content, or webpage content]

Your tasks:
1. Extract the product name
2. Identify the product category/industry
3. List 5-7 core features or capabilities
4. Describe target users/customers
5. Identify unique value propositions
6. Suggest search keywords for finding competitors

Output format (JSON):
{
  "product_name": "",
  "category": "",
  "core_features": ["", "", ...],
  "target_users": "",
  "value_propositions": ["", ""],
  "competitor_search_keywords": ["", ""]
}

Be thorough but concise. Focus on aspects relevant to finding and comparing competitors.
```

**Competitor Researcher Agent Prompt:**
```
You are a Competitor Research agent. Your role is to discover competing products through web research.

Input: Structured product description with search keywords

Your tasks:
1. Identify 10-15 likely competitors based on product category and features
2. For each competitor, provide:
   - Official name
   - Primary website URL
   - 2-3 sentence summary explaining what they do
   - Relevance score (0.0-1.0) indicating how directly they compete

Output format (JSON):
{
  "competitors": [
    {
      "name": "",
      "url": "",
      "summary": "",
      "relevance_score": 0.0
    }
  ]
}

Focus on direct competitors, not adjacent products. Prioritize active, established products.
```

**Differential Analysis Agent Prompt:** (NEW)
```
You are a Differential Analysis agent. Your role is to compare new competitor discovery results with previous analysis to identify changes in the competitive landscape.

Input: 
- Current competitor discovery results (list of competitors with URLs and summaries)
- Previous competitor list from last analysis (with dates)
- Product context

Your tasks:
1. Match current competitors with previous competitors (by name/URL similarity)
2. Identify three categories:
   - NEW: Competitors that weren't in the previous analysis
   - CONTINUING: Competitors that appear in both analyses
   - DISAPPEARED: Previous competitors not found in current analysis
3. For each competitor, provide:
   - Status: "new", "continuing", or "disappeared"
   - Explanation: Brief description of the change (if applicable)
   - Significance: How important is this change? (low/medium/high)

Output format (JSON):
{
  "competitors": [
    {
      "id": "...",
      "name": "",
      "url": "",
      "summary": "",
      "status": "new"|"continuing"|"disappeared",
      "status_explanation": "",
      "significance": "low"|"medium"|"high",
      "previous_competitor_id": null | "uuid"
    }
  ],
  "summary": {
    "new_count": 0,
    "continuing_count": 0,
    "disappeared_count": 0,
    "significant_changes": ["Brief description of important changes"]
  }
}

Be analytical and highlight truly meaningful competitive shifts, not just minor variations.
```

**Feature Extractor Agent Prompt (UPDATED):**
```
You are a Feature Extraction agent. Your role is to thoroughly research a competitor and extract their product features. You can operate in two modes: fresh extraction or comparative analysis.

Input: 
- Competitor name and URL
- Optional: Previous features from last analysis (for comparison mode)

Your tasks:

MODE 1: Fresh Extraction (no previous features provided)
1. Research the competitor's website and product information
2. Extract 15-25 distinct features or capabilities
3. For each feature, provide:
   - Feature name (concise, 2-5 words)
   - Description (1-2 sentences)
   - Category (e.g., "Core Functionality", "Integration", "Analytics", "Pricing Model")
   - Confidence score (0.0-1.0) based on information clarity
   - Source URL (specific page where found)

MODE 2: Comparative Analysis (previous features provided)
1. Extract current features as above
2. Compare with previous features to identify:
   - NEW: Features not present in previous analysis
   - MODIFIED: Features that changed (description, category, or capability)
   - REMOVED: Previous features no longer found
   - UNCHANGED: Features that remain the same
3. For each feature, add:
   - change_type: "new"|"modified"|"removed"|"unchanged"
   - change_description: Brief explanation of what changed (for modified features)
   - previous_feature_id: Link to previous feature (if applicable)

Output format (JSON):
{
  "competitor_name": "",
  "analysis_mode": "fresh"|"comparative",
  "features": [
    {
      "name": "",
      "description": "",
      "category": "",
      "confidence": 0.0,
      "source_url": "",
      "change_type": "new"|"modified"|"removed"|"unchanged",
      "change_description": "",
      "previous_feature_id": null | "uuid"
    }
  ],
  "summary": {
    "total_features": 0,
    "new_features": 0,
    "modified_features": 0,
    "removed_features": 0,
    "unchanged_features": 0
  }
}

Be specific and factual. Focus on tangible features, not marketing language. When comparing, be precise about what actually changed versus minor wording differences.
```
   - Confidence score (0.0-1.0) based on information clarity
   - Source URL (specific page where found)

Output format (JSON):
{
  "competitor_name": "",
  "features": [
    {
      "name": "",
      "description": "",
      "category": "",
      "confidence": 0.0,
      "source_url": ""
    }
  ]
}

Be specific and factual. Focus on tangible features, not marketing language.
```

**Idea Structuring Agent Prompt:**
```
You are an Idea Structuring agent. Your role is to convert competitor features into anonymized, votable feature ideas.

Input: Competitor feature with name, description, and context

Your tasks:
1. Convert the feature into a structured idea using this format:
   - What: Clear description of the feature/capability (2-3 sentences)
   - Why: Business value or user benefit (2-3 sentences)
   - Use Case: Concrete scenario showing how it would be used (2-3 sentences)

2. Anonymize: Remove all competitor-specific branding, product names, and identifiers
3. Generalize: Frame the idea as if it's a new concept, not a copy
4. Focus on value: Emphasize benefits and use cases, not just functionality

Output format (JSON):
{
  "what": "",
  "why": "",
  "use_case": ""
}

The output should be ready to submit to a feature voting system where users won't know its competitive origin.
```

### LLM Service Integration

Extend existing `LLMService` with agent-specific methods:

```python
class LLMService:
    # Existing methods...
    
    async def call_agent(
        self, 
        agent_name: str,
        prompt: str,
        input_data: Dict,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> Dict:
        """
        Generic agent caller with structured output parsing
        """
        # Build full prompt with system message
        # Call Claude API
        # Parse JSON response
        # Validate against expected schema
        # Log execution metrics
        # Return structured data
        
    async def call_with_web_search(
        self,
        prompt: str,
        search_queries: List[str]
    ) -> Dict:
        """
        Enable web search capability for research agents
        Uses Claude's web search tools
        """
```

## Testing Strategy

### Unit Tests
- Each agent's prompt construction
- Output parsing and validation
- Error handling for malformed AI responses

### Integration Tests
- End-to-end workflow from Stage 1 to Stage 5
- Parallel feature extraction
- Database transactions and rollbacks
- API endpoint responses

### AI Testing
- Sample inputs with expected output structures
- Edge cases (ambiguous products, no competitors found)
- Token usage monitoring
- Response time benchmarks

## Monitoring & Observability

### Metrics to Track
- Sessions created vs completed
- Average time per stage
- Agent execution times and token usage
- User drop-off points in workflow
- Feature extraction success rates
- Ideas generated vs submitted

### Logging
- All agent inputs/outputs in `agent_execution_logs` table
- API request/response logs
- Celery task status and failures
- User actions at each stage

## Performance Optimization

### Parallel Processing
- Use Celery for parallel competitor feature extraction
- Configurable concurrency limits
- Queue management for large batches

### Caching
- Cache competitor research results (24 hour TTL)
- Cache AI agent responses for identical inputs
- Redis for session state management

### Rate Limiting
- LLM API rate limiting (tokens per minute)
- Web search rate limiting
- Graceful degradation on limits

## Security & Compliance

### Data Handling
- User data isolation (sessions tied to user_id)
- Audit trail in agent_execution_logs
- Soft deletes for session data

### Ethical Considerations
- Respect robots.txt for web scraping
- Rate-limit competitor website access
- Clear disclosure of AI usage to users
- No storing of competitor proprietary data (only public info)

### API Security
- Require authentication for all endpoints
- Role-based access (only authenticated users)
- Input validation on all user inputs
- File upload validation (type, size limits)

## Deployment Considerations

### Environment Variables
```
ANTHROPIC_API_KEY=sk-...
MAX_COMPETITOR_DISCOVERY=15
MAX_FEATURES_PER_COMPETITOR=25
FEATURE_EXTRACTION_TIMEOUT=300  # seconds
PARALLEL_EXTRACTION_LIMIT=5     # concurrent Celery tasks
CLAUDE_MODEL=claude-sonnet-4-5-20250929
```

### Database Migrations
- Alembic migrations for all new tables
- Include indexes in migration files
- Test rollback scenarios

### Celery Configuration
- Separate queue for competitor intelligence tasks
- Configure worker concurrency based on API limits
- Set up task result backend (Redis)

## Success Metrics

### User Engagement
- % of sessions completed (all 5 stages)
- Average time to complete workflow
- Number of ideas submitted per session

### AI Performance
- Agent accuracy (human validation sample)
- Average competitors discovered per product
- Average features extracted per competitor
- Idea quality (voting performance vs manual ideas)

### System Performance
- API response times < 200ms (non-AI endpoints)
- Agent execution times < 30s (per agent call)
- Parallel extraction completion < 5 minutes (5 competitors)

## Implementation Checklist

**Phase 1: Foundation (Week 1-2)**
- [ ] Database schema and migrations
- [ ] Base agent class and LLMService integration
- [ ] API endpoint structure (stub implementations)
- [ ] Frontend wizard shell with stage navigation

**Phase 2: Agent Development (Week 2-3)**
- [ ] Product Analyzer agent
- [ ] Competitor Researcher agent
- [ ] Feature Extractor agent
- [ ] Idea Structuring agent
- [ ] Agent prompt optimization and testing

**Phase 3: Workflow Integration (Week 3-4)**
- [ ] Stage 1-2 complete integration
- [ ] Celery tasks for parallel processing
- [ ] Stage 3-4 integration
- [ ] Stage 5 finalization and idea submission

**Phase 4: Frontend Polish (Week 4-5)**
- [ ] UI components for all stages
- [ ] AI activity indicators
- [ ] Error handling and validation
- [ ] Responsive design

**Phase 5: Testing & Deployment (Week 5-6)**
- [ ] Unit and integration tests
- [ ] End-to-end testing with real data
- [ ] Performance optimization
- [ ] Documentation and deployment

## Next Steps

1. **Review this specification** with stakeholders
2. **Prioritize features** if MVP needs to be smaller
3. **Set up development environment** with Claude API access
4. **Begin with database schema** and migrations
5. **Build and test agents independently** before integration
6. **Iterate on prompts** based on real-world testing

## Questions to Consider

1. Should we add a "similarity check" before finalizing ideas to avoid duplicates with existing ideas?
2. **How should product naming conflicts be handled?** (user tries to create "MyApp" but already has "myapp")
3. Should there be admin review before competitor-generated ideas appear in voting?
4. **How long should we retain historical analysis data?** (Compliance and storage considerations)
5. Should we implement WebSockets for real-time agent activity updates, or polling?
6. **Should users be able to merge/rename products?** (e.g., rename "App" to "MyApp Pro")
7. **Should comparison mode be optional or always-on?** (Current design: optional with toggle)
8. **What's the max number of historical sessions to keep per product?** (Storage/performance tradeoff)
9. **Should we auto-archive old sessions?** (e.g., sessions > 6 months old)
10. **Should we allow comparing non-adjacent sessions?** (e.g., compare Jan 2024 with Jan 2025, skipping interim analyses)

---

**License**: MIT (matching existing project)

This specification provides a complete blueprint for building the multi-agent competitor intelligence system. Implement incrementally and test each stage thoroughly before moving to the next.
