# Competitive Intelligence & Feature Ideation System - Requirements Outline

## 1. System Overview

A program that systematically discovers competitor products, extracts their features, and generates anonymized feature ideas for internal evaluation and voting. Users can also manually submit ideas through natural language input, with intelligent duplicate detection and AI-assisted structuring.

## 2. Core Functional Requirements

### 2.1 Competitor Input Management

- **Input Interface**: Accept list of competitor companies/products
  - Support multiple input formats (manual entry, CSV upload, API)
  - Allow for competitor URLs, company names, or product names
  - Enable editing/updating competitor list over time
- **Competitor Validation**: Verify competitors exist and are accessible
- **Persistence**: Store competitor list with metadata (date added, status, last scanned)

### 2.2 Product Discovery & Confirmation

- **Automated Web Research**
  - Use LLM (Claude API or alternative) to search and identify competitor products
  - Query multiple sources: company websites, product pages, review sites, documentation
  - Extract product names, descriptions, and primary URLs
- **Product Cataloging**
  - Present discovered products to administrator for review
  - Allow confirmation/rejection of products to include in analysis
  - Support manual addition of products missed by automated discovery
- **Product Metadata Tracking**
  - Store product name, competitor association, URL, description
  - Track discovery date and confirmation status

### 2.3 Feature Extraction & Analysis

- **Automated Feature Mining**
  - Parse product pages, documentation, feature lists, and marketing materials
  - Use LLM to identify discrete features and capabilities
  - Extract feature descriptions, use cases, and benefits
- **Feature Classification**
  - Categorize features by type (e.g., UI/UX, integration, automation, analytics)
  - Identify feature maturity (beta, GA, deprecated)
  - Flag premium vs. free features when applicable

### 2.4 Feature Idea Generation

- **Idea Transformation Engine**
  - Convert each competitor feature into generalized product idea
  - **Required Elements per Idea:**
    - **What**: Clear description of functionality (vendor-neutral language)
    - **Why**: Intended value proposition and user benefit
    - **Use Case**: Generalized scenario demonstrating utility
  - **Anonymization Rules:**
    - Remove competitor-specific terminology, branding, and implementation details
    - Reframe features in terms of user problems/solutions
    - Use generic examples and scenarios
    - Ensure idea stands alone without revealing source

### 2.5 Manual Idea Submission (NEW)

- **Freeform Text Entry Interface**

  - Available to both Admins and Voters
  - Single text area for natural language input
  - No required fields or structured form initially
  - Support for any length from brief phrases to detailed descriptions
  - Auto-save draft functionality to prevent loss of work
  - Minimum character threshold (e.g., 20 characters) before triggering similarity search

- **Real-Time Similarity Detection**

  - **Automatic Search Trigger**:
    - Triggered after brief pause in typing (e.g., 2-3 seconds of inactivity)
    - Minimum text threshold met (e.g., 20-30 characters)
    - Re-triggers as user continues adding content
  - **Similarity Algorithm**:
    - Use semantic similarity via LLM embeddings or vector search
    - Compare user's raw text against existing ideas (titles + full descriptions)
    - Analyze semantic meaning, not just keyword matching
    - Configure similarity threshold (e.g., 70%+ match triggers display)
    - Weight recent typing more heavily for progressive refinement
  - **Similar Ideas Display**:
    - Non-intrusive sidebar or expandable panel (doesn't block writing)
    - Show top 3-5 potentially matching ideas ranked by similarity
    - Display similarity confidence (e.g., "85% similar" or "Highly similar")
    - Show current vote count for each similar idea
    - Include "View Full Idea" expandable section
    - Update dynamically as user types more content
    - Clear visual indicator: "We found similar ideas you might want to vote on instead"

- **User Decision Point**

  - **Option 1: Vote on Existing Idea**:
    - One-click upvote directly from similarity results
    - Cancels new idea submission
    - Records that user found match satisfactory
    - Confirmation message: "Your vote has been added to this idea"
  - **Option 2: Continue Adding Idea**:
    - User dismisses similarity results or continues typing
    - Proceeds to AI-assisted structuring phase
    - Similarity results remain accessible for reference
  - **Option 3: Cancel**:
    - Abandon submission entirely
    - Option to save as draft for later

- **LLM-Assisted Idea Structuring** (activated when user continues)

  - **Trigger**: User clicks "Continue with My Idea" or "Structure My Idea" button
  - **AI Processing**:
    - LLM analyzes freeform text to extract key concepts
    - Generates structured format with What/Why/Use Case sections
    - Preserves user's original intent and language style
    - Identifies missing components and suggests additions
  - **Interactive Refinement Interface**:
    - Display AI-generated structure in editable format:
      - **What section**: Pre-populated with extracted functionality description
      - **Why section**: Pre-populated with identified benefits/value proposition
      - **Use Case section**: Pre-populated with scenario/example
    - Each section clearly labeled and independently editable
    - Show original freeform text in collapsible reference panel
    - **AI Suggestions Panel**:
      - "Consider adding..." prompts for incomplete sections
      - Questions to help user expand (e.g., "Who would benefit most from this?")
      - Alternative phrasings for clarity
  - **Collaborative Editing**:
    - User can edit any AI-generated content directly
    - "Regenerate" button for each section if AI misunderstood
    - "Ask AI for help" button to request specific improvements
    - Real-time character count and completeness indicators
  - **Quality Checks**:
    - Warn if sections are too brief (e.g., <20 characters)
    - Flag overly technical jargon or competitor-specific terms
    - Suggest more generic language where appropriate

- **Final Submission Review**

  - Preview formatted idea as it will appear to voters
  - Optional title generation by AI if user didn't include one
  - Optional category/tag suggestions based on content
  - "Submit Idea" button only enabled when minimum quality thresholds met
  - Final similarity check with newly structured content (may find different matches)

- **Submission Confirmation**
  - Acknowledge successful submission with idea ID
  - Show link to view submitted idea in main list
  - Option to immediately vote on own idea (based on system configuration)
  - Prompt: "Want to submit another idea?"

### 2.6 Source Attribution & Tracking

- **Internal Metadata (Admin Only)**
  - **For Competitor-Sourced Ideas:**
    - Link each idea to source: competitor name, product name, specific feature
    - Store original feature description and URL
    - Track extraction date and method
    - Maintain audit trail of idea provenance
  - **For Manually-Submitted Ideas:**
    - Track submitter identity (user ID, name, timestamp)
    - **Store original freeform text input before AI structuring**
    - **Store AI-generated structured version**
    - **Track user edits to AI suggestions (acceptance rate)**
    - Record submission method (manual entry)
    - Store submission metadata (IP, user agent if relevant)
    - Link to similarity check results at submission time
    - **Record whether user saw similar ideas and chose to submit anyway**
- **Access Control**
  - Source data (competitor or submitter) visible only to administrators
  - Voting interface shows only anonymized ideas
  - Submitters can see their own submission history with original text
  - Separate database tables/views for public vs. admin data

### 2.7 Voting & Prioritization System

- **Idea Presentation**
  - Display all ideas (automated and manual) to stakeholders/voters
  - Support filtering by category, status, date added, source type
  - Include full idea description (what, why, use case)
  - Show vote count and ranking
- **Voting Mechanism**
  - Upvote/downvote functionality per idea
  - Track voter identity (optional) or allow anonymous voting
  - Calculate aggregate scores and rankings
  - **Self-Voting Policy**: Configure whether users can vote on their own submitted ideas
- **Prioritization Output**
  - Sort ideas by vote score
  - Export prioritized list with vote counts
  - Allow administrators to view source data alongside votes
  - Flag high-vote manually-submitted ideas for special attention

## 3. Technical Architecture Requirements

### 3.1 Data Storage

- **Database Schema**
  - Competitors table (name, URL, status, metadata)
  - Products table (name, competitor_id, URL, description, confirmed)
  - Features table (raw feature data, product_id, extraction_date)
  - Ideas table (anonymized content, feature_id, category, status, **source_type, submitter_id, structured_what, structured_why, structured_use_case**)
  - Votes table (idea_id, user_id, vote_value, timestamp)
  - Users table (user_id, name, email, role, created_date)
  - Submissions table (idea_id, user_id, timestamp, **original_freeform_text, ai_structured_version, user_edits_json, similarity_check_results, dismissed_similar_ideas**)
  - **Drafts table (draft_id, user_id, freeform_text, last_updated, similarity_results_cache)**
- **Data Relationships**:
  - Maintain full traceability from idea → feature → product → competitor (for automated ideas)
  - Track idea → submitter → original text → AI structuring → user edits → similarity results (for manual ideas)
  - **Source Type Enum**: 'competitor_automated', 'manual_submission'

### 3.2 LLM Integration

- **API Configuration**
  - Support Claude API (primary) with fallback to OpenAI/others
  - Configurable model selection and parameters
  - API key management and rate limiting
- **Prompt Engineering**
  - Structured prompts for product discovery
  - Feature extraction prompts with output formatting
  - Idea generation prompts with anonymization rules
  - **Similarity analysis prompts for semantic matching**
  - **Idea structuring prompts with examples (freeform → What/Why/Use Case)**
  - **Refinement prompts for improving incomplete sections**
  - **Suggestion generation prompts for helping users expand ideas**
- **Streaming Support**
  - Real-time streaming of AI-generated structured content
  - Progressive display as AI writes each section
  - Cancellable generation if user wants to restart
- **Quality Controls**
  - Validation of LLM outputs
  - Manual review queue for flagged items
  - Retry logic for failed API calls
  - **Fallback to form-based entry if AI structuring fails**

### 3.3 Similarity Detection Engine (NEW)

- **Semantic Search**
  - Generate embeddings for all existing ideas (title + full structured description)
  - Use vector database (e.g., Pinecone, Weaviate, pgvector) or in-memory similarity
  - Real-time embedding generation for freeform text as user types
  - Progressive refinement: update embeddings as user adds more content
- **Matching Algorithm**
  - Cosine similarity or semantic distance calculation
  - Configurable threshold (default: 70-80% similarity)
  - Return top 3-5 similar ideas ranked by relevance
  - **Adaptive scoring**: weight similarity higher when user text is more complete
  - **Context-aware matching**: understand intent even with brief text
- **Performance Optimization**
  - Pre-compute and cache idea embeddings
  - Incremental updates when ideas added/modified
  - Async processing for large idea databases
  - **Debouncing**: Wait for typing pause before computing similarity
  - **Caching**: Store recent similarity results to avoid redundant API calls
  - **Rate limiting**: Prevent excessive API calls during continuous typing

### 3.4 Web Scraping & Data Collection

- **Content Retrieval**
  - Web scraping capabilities (respect robots.txt)
  - Support for JavaScript-rendered content
  - Handle authentication-free public pages only
- **Rate Limiting**: Respectful crawling with delays
- **Error Handling**: Gracefully handle inaccessible pages

### 3.5 User Interface

- **Administrator Dashboard**
  - Competitor management (add/edit/remove)
  - Product confirmation workflow
  - Idea review with source attribution visible (competitor or submitter)
  - User management: View all users, submission history per user
  - **View original freeform text vs. final structured version**
  - **Analytics on AI structuring effectiveness**
  - System configuration and monitoring
  - Duplicate management: Merge similar ideas, mark as duplicates
- **Voting Interface**
  - Clean, simple idea browsing
  - Vote submission and vote history
  - Leaderboard/ranking view
  - **"Submit New Idea" button prominently displayed**
- **Manual Idea Submission Flow (NEW)**
  - **Step 1**: User clicks "Submit New Idea"
  - **Step 2**: Freeform text area with writing guidance
    - Placeholder: "Describe your feature idea in your own words..."
    - Character counter (minimum threshold indicator)
    - Auto-save indicator
  - **Step 3**: Real-time similarity detection (non-blocking)
    - Sidebar/panel shows similar ideas as user types
    - Updates dynamically without interrupting writing
    - Visual similarity scores and vote counts
  - **Step 4**: Decision point (Vote or Continue)
    - One-click voting on similar ideas
    - "None of these match - continue with my idea" option
    - Similar ideas remain visible throughout
  - **Step 5**: AI-assisted structuring (if continuing)
    - Display structured What/Why/Use Case with AI suggestions
    - Interactive editing interface
    - Original text reference panel
    - Regeneration and help options
  - **Step 6**: Final review and submission
    - Preview formatted idea
    - Final similarity check
    - Submit button
  - **Step 7**: Confirmation and return
- **User Profile/Dashboard**
  - View own submitted ideas
  - Track status and votes on own submissions
  - **View original text and structured versions**
  - Cannot see competitor source attribution
  - Access saved drafts
- **Reporting Interface**
  - Export capabilities (CSV, JSON)
  - Analytics on vote patterns
  - Source attribution reports (admin only)
  - Submission analytics: Ideas by user, acceptance rates, similarity patterns
  - **AI structuring metrics**: acceptance rate, edit frequency, quality scores

## 4. Security & Compliance Requirements

### 4.1 Data Access Controls

- **Role-Based Permissions**
  - Admin: Full access including source attribution (competitor and submitter data)
  - Voter: Access to anonymized ideas, can submit ideas, can view own submissions
  - Viewer: Read-only access to voting results
- **Authentication**: Secure login system with user identity tracking
- **Audit Logging**: Track all data access, modifications, and submissions

### 4.2 Ethical & Legal Considerations

- **Public Information Only**: System accesses only publicly available data
- **No Proprietary Data**: Do not attempt to access behind authentication/paywalls
- **Attribution Transparency**: Internal tracking allows compliance with potential disclosure requirements
- **Terms of Service Compliance**: Respect website ToS for all scraped content
- **User-Generated Content**: Clear terms for manual submissions (ownership, licensing)
- **AI Transparency**: Users informed that AI assists with structuring their ideas

### 4.3 Data Privacy

- **Anonymization Integrity**: Ensure ideas cannot be reverse-engineered to source
- **Voter Privacy**: Handle voter data per privacy policy
- **Submitter Privacy**: Submitter identity visible only to admins (not to other voters)
- **Data Retention**: Configurable retention policies for raw feature data and submission records
- **Draft Privacy**: User drafts stored securely and not visible to others

## 5. Quality Assurance Requirements

### 5.1 Validation Workflows

- **Product Discovery Review**: Admin approval before feature extraction
- **Feature Quality Check**: Sample manual review of extracted features
- **Idea Quality Review**: Spot-check anonymization effectiveness
- **Duplicate Detection**: Flag similar ideas from different sources
- **Manual Submission Review (NEW)**:
  - Optional admin approval workflow for manually submitted ideas
  - Quality check for completeness and clarity
  - **Review AI structuring quality and user acceptance**
  - Merge/consolidate duplicate manual submissions
  - **Flag ideas where users dismissed highly similar existing ideas**

### 5.2 Metrics & Monitoring

- **Discovery Metrics**: Products found, confirmation rate
- **Extraction Metrics**: Features per product, extraction success rate
- **Generation Metrics**: Ideas created, anonymization quality score
- **Engagement Metrics**: Vote participation, consensus levels
- **Submission Metrics (NEW)**:
  - Manual ideas submitted per user
  - Similarity check success rate (% users who voted instead of submitting)
  - Average similarity scores for submitted ideas
  - Duplicate detection accuracy
  - Time to decision (vote vs. submit)
  - **Freeform text length statistics**
  - **AI structuring acceptance rate (% of AI suggestions kept vs. edited)**
  - **Average time spent in structuring phase**
  - **Completion rate (drafts that became submissions)**
  - **Quality scores of manually submitted ideas vs. automated ideas**

## 6. Scalability & Performance

- **Batch Processing**: Handle multiple competitors/products in parallel
- **Incremental Updates**: Periodic re-scanning for new features
- **Caching**: Store LLM responses to minimize API costs
- **Async Operations**: Long-running tasks don't block user interface
- **Vector Search Optimization (NEW)**: Efficient similarity search even with thousands of ideas
- **Real-Time Responsiveness**:
  - Similarity checks complete within 1-2 seconds of typing pause
  - AI structuring completes within 3-5 seconds
  - Streaming AI responses for immediate feedback
- **Draft Auto-save**: Save every 10-30 seconds without impacting UI performance

## 7. Future Enhancements (Optional)

- **Trend Analysis**: Identify patterns across competitors
- **Gap Analysis**: Compare generated ideas to existing product roadmap
- **Automated Monitoring**: Alert when competitors launch new features
- **Integration**: Export prioritized ideas to project management tools (Jira, Linear, etc.)
- **ML Enhancement**: Learn from vote patterns to improve idea generation
- **Collaborative Refinement**: Allow users to suggest edits to existing ideas
- **Idea Merging**: Admin tools to combine similar ideas with vote consolidation
- **Gamification**: Badges/rewards for high-quality submissions and active voting
- **Notification System**: Alert submitters when their ideas reach vote thresholds
- **Advanced Duplicate Detection**: Use ML to identify conceptually similar ideas even with different wording
- **Voice Input**: Allow users to dictate ideas via speech-to-text
- **Multi-language Support**: AI translation and structuring in multiple languages
- **Collaborative Drafting**: Multiple users can contribute to refining an idea before submission
- **AI Learning**: System improves structuring based on user edit patterns over time
