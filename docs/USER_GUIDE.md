# Feature Voting System - User Guide

**Version**: 1.0
**Last Updated**: December 2024

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [User Voting Module](#user-voting-module)
4. [Competitive Intelligence Module](#competitive-intelligence-module)
5. [User Roles & Permissions](#user-roles--permissions)
6. [Common Workflows](#common-workflows)
7. [Tips & Best Practices](#tips--best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Introduction

The Feature Voting System is a comprehensive platform that combines user feedback collection with competitive intelligence analysis. It helps product teams:

- **Collect and prioritize user feedback** through idea submissions and voting
- **Analyze competitor products** using AI-powered feature extraction
- **Generate product ideas** by analyzing market gaps and user needs
- **Make data-driven product decisions** with integrated analytics

### Key Features

**User Voting Module**:
- Submit product ideas with structured templates
- Vote and comment on ideas
- Browse and filter ideas by category, product, or status
- Track idea evolution from submission to implementation

**Competitive Intelligence Module**:
- Create and manage product profiles
- Discover and track competitors automatically
- Extract features from competitor products using AI
- Conduct differential analysis across sessions
- Generate AI-powered product ideas based on competitive gaps

### Architecture Overview

The system consists of:
- **Backend API**: FastAPI server (Python) with SQLite database
- **Frontend**: React + TypeScript SPA with Tailwind CSS
- **AI Engine**: Claude 4.5 for natural language analysis
- **Vector Search**: Semantic similarity for feature matching

---

## Getting Started

### Installation & Setup

**Prerequisites**:
- Python 3.11+ (3.12 recommended)
- Node.js 18+
- SQLite 3
- Anthropic API key (for Competitive Intelligence features)

**Quick Setup**:

```bash
# Clone the repository
git clone <repository-url>
cd feature-voting-system

# Run complete setup and validation
./setup_and_test.sh

# Or use quick start (after initial setup)
./start.sh
```

For detailed setup instructions, see [docs/development/SETUP.md](development/SETUP.md).

### First Login

**Default Admin Credentials**:
- **Username**: `admin`
- **Password**: Configured in `backend/.env` (default: `password`)

**Important**: Change the admin password immediately after first login.

### Password Management

The system uses simplified password management for development:

**For Regular Users**:
1. Admin creates user account with temporary password
2. User logs in with temporary password
3. System prompts for new password on first login
4. No email verification required

**For Development**:
- No OTP or email verification (disabled in dev mode)
- Passwords stored using bcrypt hashing
- JWT tokens for session management (7-day expiry)

See [Password Management](development/PASSWORD_MANAGEMENT.md) for details.

### System Navigation

**Main Navigation**:
- **Ideas**: Browse and submit product ideas
- **Voting**: Vote on submitted ideas
- **Products**: Access Competitive Intelligence module
- **Admin**: User management (admin only)

**User Menu** (top-right):
- Profile settings
- Change password
- Logout

---

## User Voting Module

The User Voting Module enables teams to collect, prioritize, and manage product ideas from users and stakeholders.

### Submitting Ideas

**Idea Submission Form** has three sections:

1. **WHAT** - Describe the feature
   - Title (required)
   - Detailed description
   - Attach to product (optional)

2. **WHY** - Business justification
   - Problem this solves
   - Target users
   - Expected benefits

3. **USE CASE** - Practical application
   - Step-by-step scenario
   - User journey
   - Success criteria

**Tips for Good Ideas**:
- Be specific and actionable
- Focus on problems, not solutions
- Provide concrete use cases
- Link to relevant product if applicable

### Voting on Ideas

**Voting System**:
- Each user gets **one vote per idea**
- Votes can be changed or removed
- Vote count displayed on idea cards
- Ideas sorted by vote count (default)

**How to Vote**:
1. Browse ideas on the **Ideas** page
2. Click the upvote arrow on idea cards
3. Click again to remove your vote
4. Filter/sort to find relevant ideas

### Browsing Ideas

**Filter Options**:
- **By Product**: Show ideas for specific products only
- **By Status**: Draft, Under Review, Planned, In Progress, Completed, Rejected
- **By Category**: Custom categories configured by admin
- **Search**: Full-text search across title and description

**Sort Options**:
- Most Voted (default)
- Newest First
- Recently Updated
- Alphabetical

**Idea Card Information**:
- Title and description preview
- Vote count with voting button
- Comment count
- Status badge
- Product association (if linked)
- Submission date and author

### Commenting

**Add Comments**:
1. Click on idea card to view details
2. Scroll to **Comments** section
3. Type comment and click **Post**
4. Comments appear chronologically

**Comment Features**:
- Markdown support (bold, italic, links, code)
- Author attribution with timestamp
- Edit your own comments (within 5 minutes)
- Admin can moderate all comments

### Product-Centric Ideas

Ideas can be linked to **Products** for better organization:

**Benefits**:
- Filter ideas by product
- Track product-specific feedback
- Align ideas with competitive analysis
- Enable idea generation from competitor features

**How to Link**:
- Select product during idea submission
- Or edit idea and choose product from dropdown

---

## Competitive Intelligence Module

The Competitive Intelligence Module is a 5-stage workflow for analyzing competitors and generating product ideas.

### Overview: The 5-Stage Workflow

```
Stage 1: Product Analysis
  ↓
Stage 2: Competitor Discovery
  ↓
Stage 3: Feature Extraction
  ↓
Stage 4: Analysis & Insights
  ↓
Stage 5: Idea Generation
```

Each session progresses through these stages sequentially, with ability to return to previous stages.

---

### Stage 1: Product Analysis

**Purpose**: Define your product and extract core features from documentation.

**Inputs**:
- Product name
- Product description/documentation
- Source type: Text, URL, or File upload

**What Happens**:
1. AI analyzes your product documentation
2. Extracts **5-7 core features** (strategic level)
3. Extracts **10-25 detailed features** (tactical level)
4. Identifies product category and target users
5. Generates competitor search keywords

**Output**:
- Product profile with structured data
- Core features list (shown in summary)
- Detailed features list (for comparison)
- Recommended competitor search terms

**Tips**:
- Provide comprehensive product description
- Include feature lists, use cases, and value propositions
- Upload multiple documentation sources if available
- Review extracted features for accuracy

**Example**:
```
Product: "SalesForce Pro CRM"

Core Features (7):
- Contact management
- Sales pipeline tracking
- Email integration
- Reporting and analytics
- Mobile applications
- Team collaboration
- Custom workflows

Detailed Features (22):
- Contact management
- Custom fields for contacts
- Sales pipeline tracking
- Drag-and-drop pipeline interface
- Gmail integration
- Outlook integration
... (16 more)
```

---

### Stage 2: Competitor Discovery

**Purpose**: Identify and select competitors to analyze.

**Discovery Methods**:

1. **AI-Powered Search**
   - Uses keywords from Stage 1
   - Searches web for competitor products
   - Extracts basic information automatically
   - Shows top 5-10 candidates

2. **Manual Entry**
   - Add competitor name and URL manually
   - Useful for known competitors not found by search
   - Provide product URL for analysis

**Competitor Selection**:
- Review discovered competitors
- Select 3-5 for detailed analysis
- Click "Features Ready" badge if features already extracted
- Click **Confirm Selection** to proceed

**Competitor Card Information**:
- Competitor name
- Website URL
- Brief description (if available)
- "Features Ready" badge (if previously analyzed)

**Tips**:
- Select direct competitors (same category/use case)
- Mix of market leaders and niche players
- 3-5 competitors ideal (more = longer extraction time)
- Reuse existing feature data when available

---

### Stage 3: Feature Extraction

**Purpose**: Extract detailed features from competitor products using AI.

**Extraction Options**:

**Option 1: Use Existing Features (Instant)**
- Reuse features from previous sessions
- Shows count of existing features
- Instant - no AI extraction needed
- Best when: Competitors previously analyzed

**Option 2: Extract Fresh Features (AI)**
- Analyze competitor documentation with AI
- Extracts 10-25 features per competitor
- Takes 2-5 minutes per competitor
- Best when: First time analyzing competitor or want latest data

**Mixed Mode**:
- System automatically detects which competitors have existing features
- Shows count: "Instant for 3 • AI extraction for 2 competitors"
- Reuses existing data when available
- Extracts only for new/selected competitors

**What Gets Extracted**:
- Feature name (2-5 words)
- Feature description (1-2 sentences)
- Feature category
- Extraction confidence score (0.0-1.0)
- Source reference (where feature was found)

**Extraction Process**:
1. Select extraction option
2. Click **Start Extraction**
3. Monitor progress bar (shows per-competitor progress)
4. Review results when complete

**Tips**:
- First analysis: Always use "Extract Fresh Features"
- Subsequent sessions: Use "Existing Features" if competitors unchanged
- For updated analysis: Use "Extract Fresh" to get latest features
- Check confidence scores (0.8+ = high quality)

---

### Stage 4: Analysis & Insights

**Purpose**: Review and compare extracted features, identify patterns and gaps.

**Analysis Views**:

**Feature Comparison Table**:
- Side-by-side competitor features
- Grouped by category
- Highlights unique features (only in one competitor)
- Shows feature overlap and differentiation

**Differential Analysis** (if multiple sessions):
- Compare current session with previous sessions
- Shows feature changes (new, modified, removed)
- Tracks competitor evolution over time
- Identifies emerging trends

**Feature Statistics**:
- Total features per competitor
- Features by category breakdown
- Unique vs shared features
- Category coverage analysis

**Insights Panel**:
- AI-generated observations
- Feature gaps in your product
- Common patterns across competitors
- Differentiation opportunities

**How to Use**:
1. Review feature comparison table
2. Note unique competitor features
3. Identify features your product lacks
4. Look for patterns in feature categories
5. Export data if needed

**Tips**:
- Focus on high-confidence features (0.8+)
- Look for unique features as differentiation opportunities
- Note common features as "table stakes" for category
- Use differential analysis to spot trends

---

### Stage 5: Idea Generation

**Purpose**: Generate product ideas based on competitive analysis and market gaps.

**Idea Sources**:
1. **Feature Gaps**: Competitor features you don't have
2. **User Pain Points**: From voting module feedback
3. **Market Trends**: Emerging features across competitors
4. **Differentiation**: Unique angles based on your positioning

**Generation Options**:

**Option 1: AI-Generated Ideas**
- Based on competitive analysis from Stage 4
- Considers your product features and gaps
- Generates 5-10 actionable ideas
- Includes justification and priority

**Option 2: Manual Idea Creation**
- Create ideas directly from competitor features
- Link to specific feature gaps
- Add your own insights and context

**Generated Idea Format**:
- **Title**: Clear, actionable feature name
- **What**: Detailed description
- **Why**: Business justification (based on competitive gap)
- **Use Case**: Practical application scenario
- **Priority**: High/Medium/Low
- **Source**: Which competitor(s) inspired this

**How to Use Generated Ideas**:
1. Review AI-generated ideas
2. Edit/refine as needed
3. Select ideas to save to voting module
4. Ideas appear in Ideas list for team voting
5. Track idea progress through development

**Tips**:
- Don't implement every gap - focus on strategic features
- Consider your product positioning and differentiation
- Prioritize based on user votes and business value
- Link ideas to specific competitor features for context

---

### Differential Analysis (Advanced)

**Purpose**: Compare multiple analysis sessions to track competitor changes over time.

**When to Use**:
- Monthly/quarterly competitive reviews
- Before major product releases
- To track competitor feature velocity
- To validate market trends

**How to Conduct**:
1. Create new session for same product
2. Select same competitors (or updated list)
3. Extract fresh features
4. System automatically compares with previous sessions
5. View change report in Stage 4

**Change Types**:
- **New Features**: Competitor added since last session
- **Modified Features**: Description or category changed
- **Removed Features**: No longer present in competitor
- **Unchanged Features**: Same as previous session

**Insights from Differential**:
- Competitor development velocity
- Feature trends (what's being added/removed)
- Your product's relative position
- Emerging market patterns

**Tips**:
- Conduct differential analysis quarterly
- Track same competitors consistently
- Note why features were removed (deprecated? renamed?)
- Use trends to inform product roadmap

---

### Session Management

**Session List** (Product Detail Page):
- View all analysis sessions for a product
- See session date, stage, and status
- Resume incomplete sessions
- Start new sessions
- Delete old sessions

**Session Actions**:
- **Resume**: Continue from last completed stage
- **View**: Review session data (read-only)
- **Delete**: Remove session and all data
- **Clone**: Create new session from existing configuration

**Session Status**:
- **In Progress**: Currently working through stages
- **Completed**: All 5 stages finished
- **Abandoned**: Started but not completed (30+ days old)

---

## User Roles & Permissions

The system uses role-based access control (RBAC) for both voting and competitive intelligence features.

### System Roles

**1. Administrator**
- Full system access
- User management (create, edit, delete users)
- Access all products and sessions
- Moderate ideas and comments
- Configure system settings

**2. Product Manager**
- Create and manage products
- Create analysis sessions
- Invite team members to products
- View all ideas (not restricted to own products)
- Submit and vote on ideas

**3. User** (Standard)
- Submit ideas
- Vote on ideas
- Comment on ideas
- View public products
- Access products they're invited to

**4. Viewer** (Read-Only)
- View ideas and products
- View analysis sessions
- Cannot submit ideas or vote
- Cannot create sessions

### Product-Level Permissions

Products use three permission levels:

**1. ADMIN**
- Full control over product
- Manage sessions
- Invite/remove team members
- Delete product
- Change product permissions

**2. EDIT**
- Create and run analysis sessions
- Extract features
- Generate ideas
- View all product data
- Cannot manage permissions

**3. VIEW**
- Read-only access to product
- View analysis sessions
- View extracted features
- Cannot create sessions
- Cannot modify data

**Permission Inheritance**:
- System Admin → Product ADMIN on all products
- Product Owner → Product ADMIN (creator)
- Invited Users → Permission level assigned by admin

---

## Common Workflows

### Workflow 1: Conducting Competitive Analysis

**Scenario**: You want to analyze 3 competitors and generate product ideas.

**Steps**:
1. Navigate to **Products** → **Create Product**
2. Enter product name and comprehensive description
3. Click **Analyze Product** (Stage 1)
4. Review extracted features, click **Confirm**
5. Stage 2: Review AI-discovered competitors
6. Select 3 competitors, click **Confirm Selection**
7. Stage 3: Choose **Extract Fresh Features**
8. Wait for extraction (2-5 min per competitor)
9. Stage 4: Review feature comparison table
10. Note feature gaps and unique competitor features
11. Stage 5: Click **Generate Ideas**
12. Review and select ideas to save to voting module
13. Team votes on generated ideas
14. Implement top-voted ideas

**Time Required**: 30-45 minutes

---

### Workflow 2: Monthly Competitive Review

**Scenario**: Track competitor changes monthly with differential analysis.

**Steps**:
1. Navigate to existing product
2. Click **New Session** to create monthly review session
3. Stage 1: Skip (product already analyzed) or re-analyze if product changed
4. Stage 2: Select same competitors as last month
5. Stage 3: Choose **Extract Fresh Features** (to get latest)
6. Wait for extraction
7. Stage 4: View **Differential Analysis** report
8. Review **New Features** added by competitors
9. Review **Removed Features** (deprecated/renamed)
10. Note trends and patterns
11. Stage 5: Generate ideas for critical gaps
12. Update product roadmap based on findings

**Time Required**: 20-30 minutes

---

### Workflow 3: User Idea Submission & Voting

**Scenario**: Collect and prioritize user feedback.

**Steps**:
1. User submits idea via **Submit Idea** form
2. Fills WHAT, WHY, USE CASE sections
3. Links to product (if applicable)
4. Submits idea
5. Team members browse **Ideas** page
6. Vote on ideas they support
7. Comment to discuss details
8. Product manager reviews top-voted ideas
9. Sets status to "Planned" for roadmap inclusion
10. Updates status as development progresses
11. Sets to "Completed" when shipped

**Time Required**: 5 minutes (submission), ongoing (voting)

---

### Workflow 4: Product-Centric Idea Management

**Scenario**: Manage ideas for a specific product with competitive context.

**Steps**:
1. Create product in Competitive Intelligence
2. Run competitive analysis (Workflow 1)
3. Generate AI ideas based on competitive gaps
4. Ideas automatically linked to product
5. Team votes on generated + user-submitted ideas
6. Filter ideas by product to see focused list
7. Compare ideas to competitor features in analysis
8. Prioritize ideas with competitive context
9. Implement and track progress

**Time Required**: Ongoing

---

## Tips & Best Practices

### For Competitive Analysis

**Product Analysis**:
- Provide comprehensive documentation (feature lists, use cases, value props)
- Upload multiple sources if available (website, docs, marketing materials)
- Review extracted features for accuracy before proceeding
- Update product analysis when major features ship

**Competitor Selection**:
- Choose 3-5 direct competitors (not too many)
- Mix market leaders with niche players
- Reuse feature data when competitors haven't changed
- Add manual competitors if AI search misses them

**Feature Extraction**:
- First analysis: Always use "Extract Fresh Features"
- Subsequent sessions: Use existing features if competitors unchanged
- Check confidence scores (0.8+ is high quality)
- Review extracted features before generating ideas

**Differential Analysis**:
- Conduct monthly or quarterly (consistent schedule)
- Track same competitors for meaningful trends
- Document why features appear/disappear
- Use insights to inform roadmap planning

**Idea Generation**:
- Don't implement every competitor feature blindly
- Consider your product positioning and differentiation
- Combine competitive gaps with user-voted ideas
- Prioritize based on strategic value, not just presence

### For User Voting

**Submitting Ideas**:
- Be specific and actionable in descriptions
- Focus on problems, not specific solutions
- Provide concrete use cases and examples
- Link to product for better organization

**Voting Strategy**:
- Vote on ideas you'd actually use
- Don't vote on everything
- Read full description before voting
- Use comments to discuss and refine

**Managing Ideas** (Admins):
- Review top-voted ideas regularly
- Set status to keep users informed
- Merge duplicate ideas
- Provide feedback via comments on rejected ideas

### General Best Practices

**Session Management**:
- Complete sessions in one sitting when possible
- Name sessions descriptively ("Q4 2024 Review")
- Delete abandoned sessions to reduce clutter
- Use session notes to document decisions

**Team Collaboration**:
- Invite team members to products (appropriate permission level)
- Use comments for discussion and refinement
- Share analysis results before idea generation
- Vote as team on generated ideas

**Data Quality**:
- Review AI-extracted data for accuracy
- Edit features if descriptions are unclear
- Report issues with low-confidence extractions
- Validate competitor URLs before extraction

**Performance**:
- Extract features for 3-5 competitors max per session
- Use existing features when available
- Schedule large analyses during off-hours
- Clear browser cache if UI feels slow

---

## Troubleshooting

### Common Issues

**"Features Ready" badge not showing**
- **Cause**: Features may be in session-specific table but not global
- **Solution**: System checks both tables automatically (fixed in v1.0)
- **If persists**: Contact administrator to check database

**Extraction showing deselected competitors**
- **Cause**: Previously extracted features cached
- **Solution**: Return to Stage 2, deselect unwanted competitors, proceed to Stage 3
- **System**: Now filters by selection status (fixed in v1.0)

**"(Instant)" showing when extraction is needed**
- **Cause**: Mixed mode (some competitors have features, some don't)
- **Solution**: Check specific count: "Instant for X • AI extraction for Y competitors"
- **System**: Label removed when extraction needed (fixed in v1.0)

**Login fails with "Unauthorized"**
- **Cause**: Incorrect credentials or expired token
- **Solution**: Verify username/password, clear browser cache, try again
- **Admin**: Reset user password if needed

**Server not starting**
- **Cause**: Port already in use or environment issues
- **Solution**:
  ```bash
  # Check for existing processes
  lsof -ti :8000 :5173

  # Kill existing processes
  ./start.sh  # Will prompt to stop existing servers

  # Or manually
  kill $(lsof -ti :8000 :5173)
  ```

**Database errors after update**
- **Cause**: Schema changes require migration
- **Solution**: Run database reset (see Development Setup)
  ```bash
  cd backend
  python reset_db.py
  ```

**AI extraction fails**
- **Cause**: Invalid API key, rate limit, or network issue
- **Solution**:
  - Check `backend/.env` has valid `ANTHROPIC_API_KEY`
  - Verify key starts with `sk-ant-`
  - Check API quota at console.anthropic.com
  - Retry extraction after waiting

**Slow performance**
- **Cause**: Large database, many features, or browser cache
- **Solution**:
  - Clear browser cache and reload
  - Close unused browser tabs
  - Check backend logs for errors
  - Restart servers with `./start.sh`

### Getting Help

**Documentation**:
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) - System architecture details
- [docs/development/SETUP.md](development/SETUP.md) - Setup and configuration
- [docs/CHEATSHEET.md](CHEATSHEET.md) - Quick reference

**Developer Resources**:
- API Documentation: http://localhost:8000/docs (when running)
- Database Schema: [docs/database_schema.sql](database_schema.sql)
- Requirements: [docs/requirements.md](requirements.md)

**Support**:
- Check recent changelogs for known issues
- Review GitHub issues (if applicable)
- Contact system administrator

---

## Appendix

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Global search |
| `Ctrl+Enter` | Submit form |
| `/` | Focus search |
| `Esc` | Close modal |

### API Rate Limits

- **Anthropic API**: 50 requests/minute (subject to plan)
- **Feature Extraction**: ~2-5 minutes per competitor
- **Idea Generation**: ~30 seconds per batch

### Browser Compatibility

**Supported**:
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Not Supported**:
- Internet Explorer
- Chrome < 90
- Firefox < 88

### Data Retention

- **Ideas**: Retained indefinitely
- **Sessions**: Retained until manually deleted
- **Features**: Retained and reused across sessions
- **Logs**: 7 days (backend), 20 files (rotating)

---

**End of User Guide**

For development setup, testing, and contribution guidelines, see [docs/development/](development/).
