"""
Seed script for demo data.

Creates realistic demo data including a demo product, users with
product permissions, ideas, votes, comments, and status history.
Idempotent — safe to re-run. Uses get-or-create patterns.

Usage:
    cd backend && ./venv/bin/python -m scripts.seed_demo_data
    cd backend && ./venv/bin/python -m scripts.seed_demo_data --cleanup
"""

import sys
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.competitor_intelligence import CIProduct, ProductPermission, ProductPermissionLevel
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.idea_lifecycle_status import IdeaLifecycleStatus
from app.models.vote import Vote
from app.models.idea_comment import IdeaComment
from app.models.idea_status_history import IdeaStatusHistory
from app.utils.security import hash_password

SEED_EMAIL_DOMAIN = "@voteflow.dev"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEMO_PASSWORD = "demo1234"

DEMO_PRODUCT = {
    "product_name": "Concur Invoice",
    "product_description": (
        "Concur Invoice is an accounts payable automation platform that helps "
        "organizations streamline invoice processing, automate approval workflows, "
        "and gain visibility into supplier spending. Features include invoice capture, "
        "three-way PO matching, configurable approval routing, and integration with "
        "major ERP systems."
    ),
    "product_category": "Accounts Payable Automation Software",
}

DEMO_USERS = [
    # (username, email, full_name, role)
    ("demo_admin", "demo_admin@voteflow.dev", "Dana Morrison", UserRole.ADMIN),
    ("demo_po_1", "po1@voteflow.dev", "Jordan Reeves", UserRole.PRODUCT_OWNER),
    ("demo_po_2", "po2@voteflow.dev", "Casey Park", UserRole.PRODUCT_OWNER),
    ("voter_01", "voter01@voteflow.dev", "Alex Chen", UserRole.VOTER),
    ("voter_02", "voter02@voteflow.dev", "Maria Santos", UserRole.VOTER),
    ("voter_03", "voter03@voteflow.dev", "James Wilson", UserRole.VOTER),
    ("voter_04", "voter04@voteflow.dev", "Priya Sharma", UserRole.VOTER),
    ("voter_05", "voter05@voteflow.dev", "Tom Baker", UserRole.VOTER),
    ("voter_06", "voter06@voteflow.dev", "Sarah Kim", UserRole.VOTER),
    ("voter_07", "voter07@voteflow.dev", "David Liu", UserRole.VOTER),
    ("voter_08", "voter08@voteflow.dev", "Emma Rodriguez", UserRole.VOTER),
    ("voter_09", "voter09@voteflow.dev", "Kevin Patel", UserRole.VOTER),
    ("voter_10", "voter10@voteflow.dev", "Lisa Nguyen", UserRole.VOTER),
    ("voter_11", "voter11@voteflow.dev", "Ryan O'Brien", UserRole.VOTER),
    ("voter_12", "voter12@voteflow.dev", "Sophia Martinez", UserRole.VOTER),
]

LIFECYCLE_STATUSES = [
    # (name, slug, color, position)
    ("On Roadmap", "on_roadmap", "#3B82F6", 0),
    ("In Development", "in_development", "#F59E0B", 1),
    ("Delivered", "delivered", "#10B981", 2),
]

# ---------------------------------------------------------------------------
# Idea templates — AP Automation / Invoice Management domain
# ---------------------------------------------------------------------------

AP_AUTOMATION_IDEAS = [
    # === ACCEPTED ideas (will be visible on board) ===
    # Hot ideas (high votes)
    {
        "title": "Slack Notifications for Invoice Approval Deadlines",
        "what": "Real-time Slack alerts when invoices are approaching their approval deadline or have been sitting in the queue too long.",
        "why": "AP teams miss approval deadlines when they're buried in email. Slack is where our teams already collaborate, so surfacing time-sensitive invoice actions there reduces late payments and early-pay discount losses.",
        "use_case": "AP manager receives a Slack DM at 9am listing 3 invoices due for approval today. They can tap 'Approve' directly from the Slack message or click through to Concur Invoice for details.",
        "category": "Integrations",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": "in_development",
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "hot",
    },
    {
        "title": "Predictive Cash Flow Dashboard from Invoice Pipeline",
        "what": "A dashboard that projects future cash outflows based on pending invoices, approval velocity, and historical payment patterns.",
        "why": "Treasury teams lack visibility into upcoming AP obligations. They manually pull reports from multiple systems to forecast cash needs, causing inaccurate forecasts and excess reserve requirements.",
        "use_case": "CFO opens the dashboard on Monday morning and sees projected outflows for the next 30/60/90 days, broken down by vendor category and payment method, with confidence intervals based on historical approval timing.",
        "category": "Analytics",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": "on_roadmap",
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "hot",
    },
    {
        "title": "AI-Powered Invoice Data Extraction from PDF Attachments",
        "what": "Automatic extraction of line-item details, PO numbers, and payment terms from scanned PDF invoices using AI/OCR.",
        "why": "Manual data entry from PDF invoices is the biggest time sink for AP clerks. It's error-prone and creates a bottleneck that delays the entire approval workflow.",
        "use_case": "AP clerk uploads a stack of 20 vendor PDFs. The system extracts header info (vendor, amount, date, PO#) and line items within seconds, pre-populating the invoice record for review rather than manual entry.",
        "category": "AI/Automation",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": "in_development",
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "hot",
    },
    # Moderate ideas
    {
        "title": "Bulk Approval Actions for Low-Risk Invoices",
        "what": "Allow approvers to select and approve multiple invoices at once when they fall below a configurable risk threshold.",
        "why": "Approvers spend time clicking through dozens of routine invoices individually. For recurring vendor invoices under $500 that match a PO, one-click batch approval would save hours per week.",
        "use_case": "Approver sees a filtered list of 15 low-risk invoices (PO-matched, known vendor, under threshold). They select all and approve in one action, with an audit log capturing the batch decision.",
        "category": "UX",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": "on_roadmap",
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "moderate",
    },
    {
        "title": "NetSuite GL Code Sync for Invoice Coding",
        "what": "Two-way sync of GL account codes between Concur Invoice and NetSuite so coding updates in either system are reflected automatically.",
        "why": "When finance adds new GL codes in NetSuite, AP has to manually update Concur's code list. Mismatches cause posting errors and reconciliation delays at month-end close.",
        "use_case": "Finance controller adds a new GL code in NetSuite for a new department. Within an hour, the code appears in Concur Invoice's coding dropdown and AP clerks can immediately assign invoices to it.",
        "category": "Integrations",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": None,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "moderate",
    },
    {
        "title": "Vendor Self-Service Portal for Invoice Status",
        "what": "A portal where vendors can check the status of their submitted invoices without contacting the AP team.",
        "why": "AP teams spend 20-30% of their time answering vendor inquiries about payment status. A self-service portal eliminates these calls and improves vendor relationships.",
        "use_case": "A vendor logs into the portal, searches by invoice number, and sees that their invoice was received, is currently in approval step 2 of 3, and has an estimated payment date of March 15.",
        "category": "UX",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": None,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "moderate",
    },
    {
        "title": "Duplicate Invoice Detection with Fuzzy Matching",
        "what": "Automatic detection of duplicate invoices using fuzzy matching on vendor name, amount, date, and invoice number — catching near-duplicates that exact matching misses.",
        "why": "Duplicate payments cost companies 0.1-0.5% of total AP spend. Vendors sometimes submit the same invoice with slightly different formatting, and exact-match detection misses these.",
        "use_case": "AP clerk submits an invoice for $12,450 from 'Acme Corp.' The system flags a potential duplicate from 'ACME Corporation' for the same amount submitted 3 days ago. The clerk reviews and confirms it's a duplicate.",
        "category": "AI/Automation",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": "on_roadmap",
        "source_type": SourceType.COMPETITOR_AUTOMATED,
        "source_metadata": {"competitor_name": "Stampli", "feature_name": "AI-Powered Duplicate Detection"},
        "vote_tier": "moderate",
    },
    {
        "title": "Mobile Invoice Capture with Receipt Matching",
        "what": "Mobile app feature to photograph receipts and invoices in the field, with automatic matching to open POs.",
        "why": "Field teams and traveling employees receive paper invoices that get lost before reaching AP. Mobile capture at the point of receipt eliminates this gap.",
        "use_case": "Sales rep receives a paper invoice from a supplier at a trade show. They snap a photo with the Concur app, which OCRs the data and matches it to PO #4521. AP receives the digitized invoice within minutes.",
        "category": "UX",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": None,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "moderate",
    },
    {
        "title": "Custom Approval Workflows by Invoice Type",
        "what": "Configure different approval chains based on invoice attributes like vendor category, amount range, cost center, or GL code.",
        "why": "One-size-fits-all approval workflows cause bottlenecks. Capital expenditure invoices need different approvers than recurring SaaS subscriptions, but currently both follow the same chain.",
        "use_case": "Admin configures rules: utility invoices under $1K auto-approve, IT invoices go to IT Director, invoices over $50K require VP + CFO approval. Each rule triggers the appropriate workflow automatically.",
        "category": "Performance",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": "delivered",
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "moderate",
    },
    # Low/new ideas
    {
        "title": "Automated Three-Way Matching Reports",
        "what": "Scheduled reports showing match rates between POs, goods receipts, and invoices with drill-down into exceptions.",
        "why": "AP managers need visibility into matching efficiency to identify problematic vendors or categories. Currently they export data to Excel to build these reports manually.",
        "use_case": "AP manager receives a weekly report showing 94% three-way match rate, with the top 5 vendors by exception volume and the most common mismatch reasons (quantity vs. price vs. missing receipt).",
        "category": "Analytics",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": None,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "low",
    },
    {
        "title": "API Endpoint for Invoice Submission from ERP",
        "what": "A REST API that allows ERP systems to push invoices directly into Concur Invoice, skipping manual upload.",
        "why": "Companies with multiple ERPs or legacy systems need programmatic invoice submission. The current email/upload process creates manual work and delays.",
        "use_case": "IT team configures their SAP ERP to POST invoice records to Concur's API whenever a new vendor invoice is recorded. The invoice appears in Concur within seconds, pre-coded and ready for approval.",
        "category": "API",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": None,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "vote_tier": "low",
    },
    {
        "title": "Supplier Spend Analytics by Category and Region",
        "what": "Interactive analytics showing spend concentration across vendor categories, regions, and time periods with trend analysis.",
        "why": "Procurement teams need spend visibility to negotiate better contracts and identify consolidation opportunities. Currently they build these views in separate BI tools.",
        "use_case": "Procurement director filters spend by 'IT Services' category and sees that 60% of spend goes to 3 vendors in North America, while EMEA spend is fragmented across 15 vendors — highlighting a consolidation opportunity.",
        "category": "Analytics",
        "status": IdeaStatus.ACCEPTED,
        "lifecycle_slug": None,
        "source_type": SourceType.CRM_IMPORT,
        "source_metadata": {"crm_source": "Salesforce", "account_name": "Global Logistics Corp", "activity_type": "feature_request"},
        "vote_tier": "low",
    },

    # === PENDING ideas (triage queue) ===
    {
        "title": "Automated Currency Conversion for Multi-Currency Invoices",
        "what": "Automatic conversion of foreign currency invoices to the company's base currency using real-time exchange rates at the time of receipt.",
        "why": "AP teams processing international invoices manually look up exchange rates and calculate conversions, which is slow and error-prone. Automated conversion would speed up processing and improve accuracy.",
        "use_case": "AP receives a EUR 8,500 invoice from a German supplier. The system automatically converts it to USD 9,180 using that day's ECB rate and flags any invoices where the vendor's stated USD amount differs by more than 2%.",
        "category": "AI/Automation",
        "status": IdeaStatus.PENDING,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "triage": {
            "confidence": 0.88,
            "reasoning": "This is a well-defined feature request addressing a clear pain point in multi-currency AP processing. The use case is specific and the value proposition is quantifiable. Recommend acceptance.",
            "recommendation": "accept",
        },
        "vote_tier": "none",
    },
    {
        "title": "Configurable Payment Term Defaults by Vendor Tier",
        "what": "Set default payment terms (Net 30, Net 60, 2/10 Net 30) by vendor tier so new invoices from tiered vendors automatically inherit the correct terms.",
        "why": "AP clerks manually set payment terms on each invoice. For vendors with negotiated terms, this is repetitive and errors lead to missed early-pay discounts or late fees.",
        "use_case": "Finance sets Tier 1 vendors (top 20 by spend) to '2/10 Net 30' and Tier 2 vendors to 'Net 45'. When a new invoice from a Tier 1 vendor arrives, it automatically inherits the 2/10 Net 30 terms.",
        "category": "Performance",
        "status": IdeaStatus.PENDING,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "triage": {
            "confidence": 0.72,
            "reasoning": "Reasonable feature request for vendor management. The implementation scope is moderate — requires a vendor tiering system and term inheritance logic. Some overlap with existing vendor management features.",
            "recommendation": "accept",
        },
        "vote_tier": "none",
    },
    {
        "title": "Integrate with Coupa for Procurement-to-Pay Visibility",
        "what": "Bidirectional integration with Coupa procurement platform to provide end-to-end visibility from requisition through payment.",
        "why": "Companies using Coupa for procurement and Concur for AP have a visibility gap between purchase request and invoice payment. This integration would close that gap.",
        "use_case": "Procurement team creates a purchase order in Coupa. When the corresponding invoice arrives in Concur, it automatically links to the Coupa PO and shows the full procurement-to-pay timeline.",
        "category": "Integrations",
        "status": IdeaStatus.PENDING,
        "source_type": SourceType.COMPETITOR_AUTOMATED,
        "source_metadata": {"competitor_name": "Coupa Invoice", "feature_name": "Unified Procure-to-Pay"},
        "competitive_context": {
            "competitors_with_feature": ["Coupa Invoice"],
            "competitive_urgency": "medium",
        },
        "triage": {
            "confidence": 0.45,
            "reasoning": "This is a strategic integration request. Coupa is a direct competitor in the AP space, so integrating with them has competitive implications. Needs product strategy review before acceptance.",
            "recommendation": "review",
        },
        "vote_tier": "none",
    },

    # === NEEDS_REVIEW ideas ===
    {
        "title": "Blockchain-Based Invoice Verification",
        "what": "Use blockchain technology to create an immutable record of invoice submissions and approvals for audit purposes.",
        "why": "Current audit trails can be modified by database admins. Blockchain would provide tamper-proof verification of the entire invoice lifecycle.",
        "use_case": "Auditors query the blockchain ledger to verify that invoice #INV-2024-1234 was submitted on Jan 15, approved by John on Jan 17, and paid on Jan 22, with cryptographic proof that no records were altered.",
        "category": "Performance",
        "status": IdeaStatus.NEEDS_REVIEW,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "triage": {
            "confidence": 0.35,
            "reasoning": "While audit trail integrity is important, blockchain may be over-engineered for this use case. Existing database audit logs with proper access controls achieve similar goals at lower complexity. The ROI is questionable given the implementation cost. Flagged for PM review.",
            "recommendation": "review",
        },
        "vote_tier": "none",
    },
    {
        "title": "Voice-Activated Invoice Lookup via Alexa/Google Assistant",
        "what": "Ask a voice assistant to check invoice status, outstanding amounts, or approval queue length.",
        "why": "AP managers on the go could get quick status updates without opening the app or logging into a computer.",
        "use_case": "AP manager says 'Hey Google, what's the total value of invoices pending my approval?' and gets a spoken response: 'You have 12 invoices pending approval totaling $47,230.'",
        "category": "UX",
        "status": IdeaStatus.NEEDS_REVIEW,
        "source_type": SourceType.SUPPORT_TICKET,
        "source_metadata": {"ticket_id": "SUPPORT-4521", "priority": "low"},
        "triage": {
            "confidence": 0.30,
            "reasoning": "Novel idea but raises significant security concerns — voice assistants in shared environments could expose financial data. The use case is niche (AP managers rarely need hands-free access). Low customer demand signal. Flagged for PM review.",
            "recommendation": "review",
        },
        "vote_tier": "none",
    },

    # === DUPLICATE idea ===
    {
        "title": "Smart Invoice OCR with Machine Learning",
        "what": "Use machine learning to read and extract data from invoice images and PDFs automatically.",
        "why": "Typing invoice data manually is slow and leads to mistakes. ML-based OCR would be faster and more accurate than traditional OCR.",
        "use_case": "Upload a batch of invoice PDFs and have the system automatically populate all fields with high accuracy, learning from corrections over time.",
        "category": "AI/Automation",
        "status": IdeaStatus.DUPLICATE,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "duplicate_of_title": "AI-Powered Invoice Data Extraction from PDF Attachments",
        "similarity": 0.89,
        "vote_tier": "none",
    },

    # === FEATURE_EXISTS idea ===
    {
        "title": "Email-Based Invoice Submission",
        "what": "Allow vendors to submit invoices by emailing them to a dedicated AP email address.",
        "why": "Many small vendors don't want to use a portal. Email submission is the simplest way for them to send invoices.",
        "use_case": "Vendor emails invoice PDF to ap-invoices@company.com. The system automatically ingests the attachment and creates an invoice record.",
        "category": "Integrations",
        "status": IdeaStatus.FEATURE_EXISTS,
        "source_type": SourceType.CUSTOMER_SUBMISSION,
        "triage": {
            "confidence": 0.92,
            "reasoning": "This feature already exists in Concur Invoice as 'Email Invoice Capture'. The submitter may not be aware of the existing functionality. Auto-response recommended.",
            "recommendation": "feature_exists",
        },
        "vote_tier": "none",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_or_create_user(db, username, email, full_name, role):
    """Get existing user by username or create new one."""
    user = db.query(User).filter(User.username == username).first()
    if user:
        return user, False
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password=hash_password(DEMO_PASSWORD),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user, True


def get_or_create_product(db, product_name, product_description, product_category, created_by_user_id):
    """Get existing product by name or create new one."""
    product = db.query(CIProduct).filter(CIProduct.product_name == product_name).first()
    if product:
        return product, False
    product = CIProduct(
        product_name=product_name,
        product_description=product_description,
        product_category=product_category,
        created_by_user_id=created_by_user_id,
    )
    db.add(product)
    db.flush()
    return product, True


def grant_permission_if_not_exists(db, product_id, user_id, level, granted_by_user_id):
    """Grant product permission if not already granted."""
    existing = db.query(ProductPermission).filter(
        ProductPermission.product_id == product_id,
        ProductPermission.user_id == user_id,
    ).first()
    if existing:
        return False
    perm = ProductPermission(
        product_id=product_id,
        user_id=user_id,
        permission_level=level,
        granted_by_user_id=granted_by_user_id,
    )
    db.add(perm)
    return True


def get_or_create_lifecycle_status(db, name, slug, color, position):
    """Get existing lifecycle status by slug or create new one."""
    status = db.query(IdeaLifecycleStatus).filter(
        IdeaLifecycleStatus.slug == slug
    ).first()
    if status:
        return status, False
    status = IdeaLifecycleStatus(
        name=name,
        slug=slug,
        color=color,
        position=position,
        is_default=True,
        is_active=True,
    )
    db.add(status)
    db.flush()
    return status, True


def create_idea_if_not_exists(db, title, product_id, **kwargs):
    """Create idea if one with the same title doesn't already exist for this product."""
    existing = db.query(Idea).filter(
        Idea.title == title,
        Idea.product_id == product_id,
    ).first()
    if existing:
        return existing, False
    idea = Idea(title=title, product_id=product_id, **kwargs)
    db.add(idea)
    db.flush()
    return idea, True


def add_vote_if_not_exists(db, idea_id, user_id):
    """Add an upvote if user hasn't already voted on this idea."""
    existing = db.query(Vote).filter(
        Vote.idea_id == idea_id,
        Vote.user_id == user_id,
    ).first()
    if existing:
        return False
    vote = Vote(idea_id=idea_id, user_id=user_id, vote_value=1)
    db.add(vote)
    return True


def add_comment(db, idea_id, user_id, text, is_system=False):
    """Add a comment to an idea."""
    comment = IdeaComment(
        idea_id=idea_id,
        user_id=user_id,
        comment_text=text,
        is_system_generated=is_system,
    )
    db.add(comment)


def add_status_history(db, idea_id, prev_status, new_status, user_id=None,
                       is_automated=False, source="submission", comment=None, confidence=None):
    """Add a status history entry."""
    entry = IdeaStatusHistory(
        idea_id=idea_id,
        previous_status=prev_status,
        new_status=new_status,
        changed_by_user_id=user_id,
        is_automated=is_automated,
        change_source=source,
        comment=comment,
        confidence=confidence,
    )
    db.add(entry)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed():
    db = SessionLocal()
    try:
        # --- Users ---
        print("Creating users...")
        users = {}
        created_count = 0
        for username, email, full_name, role in DEMO_USERS:
            user, created = get_or_create_user(db, username, email, full_name, role)
            users[username] = user
            if created:
                created_count += 1
        db.commit()
        print(f"  {created_count} new users created, {len(DEMO_USERS) - created_count} already existed")

        # Collect user references
        voter_users = [users[f"voter_{i:02d}"] for i in range(1, 13)]
        po_user = users["demo_po_1"]
        po_user_2 = users["demo_po_2"]
        admin_user = users["demo_admin"]

        # --- Product ---
        print("Creating demo product...")
        product, product_created = get_or_create_product(
            db,
            DEMO_PRODUCT["product_name"],
            DEMO_PRODUCT["product_description"],
            DEMO_PRODUCT["product_category"],
            created_by_user_id=admin_user.id,
        )
        db.commit()
        if product_created:
            print(f"  Created product: {product.product_name} (ID={product.id})")
        else:
            print(f"  Using existing product: {product.product_name} (ID={product.id})")

        # --- Product Permissions ---
        print("Granting product permissions...")
        perms_created = 0

        # POs get OWNER on the product
        for po in [po_user, po_user_2]:
            if grant_permission_if_not_exists(
                db, product.id, po.id,
                ProductPermissionLevel.OWNER, admin_user.id
            ):
                perms_created += 1

        # Voters get VIEW on the product
        for voter in voter_users:
            if grant_permission_if_not_exists(
                db, product.id, voter.id,
                ProductPermissionLevel.VIEW, admin_user.id
            ):
                perms_created += 1

        db.commit()
        print(f"  {perms_created} new permissions granted")

        # --- Lifecycle Statuses ---
        print("Creating lifecycle statuses...")
        lifecycle_map = {}
        created_count = 0
        for name, slug, color, position in LIFECYCLE_STATUSES:
            status, created = get_or_create_lifecycle_status(db, name, slug, color, position)
            lifecycle_map[slug] = status
            if created:
                created_count += 1
        db.commit()
        print(f"  {created_count} new statuses created, {len(LIFECYCLE_STATUSES) - created_count} already existed")

        # --- Ideas ---
        print("Creating ideas...")
        idea_objects = []  # (idea, template) pairs for vote/comment assignment
        ideas_created = 0
        duplicate_target = None  # Will be set when we create the OCR idea

        for idx, tmpl in enumerate(AP_AUTOMATION_IDEAS):
            # Determine is_active from status
            is_active = tmpl["status"] == IdeaStatus.ACCEPTED

            # Build idea kwargs
            kwargs = {
                "what_description": tmpl["what"],
                "why_description": tmpl["why"],
                "use_case_description": tmpl["use_case"],
                "category": tmpl.get("category"),
                "status": tmpl["status"],
                "is_active": is_active,
                "source_type": tmpl.get("source_type", SourceType.CUSTOMER_SUBMISSION),
            }

            # Assign submitter for customer submissions (deterministic by index)
            if tmpl.get("source_type") in (SourceType.CUSTOMER_SUBMISSION, SourceType.SUPPORT_TICKET):
                kwargs["submitter_id"] = voter_users[idx % len(voter_users)].id

            # Source metadata
            if tmpl.get("source_metadata"):
                kwargs["source_metadata"] = tmpl["source_metadata"]

            # Competitive context
            if tmpl.get("competitive_context"):
                kwargs["competitive_context"] = tmpl["competitive_context"]

            # Triage metadata
            if tmpl.get("triage"):
                triage = tmpl["triage"]
                kwargs["triage_confidence"] = triage.get("confidence")
                kwargs["triage_reasoning"] = triage.get("reasoning")
                kwargs["triage_recommendation"] = triage.get("recommendation")

            # Lifecycle status (only for accepted ideas)
            lifecycle_slug = tmpl.get("lifecycle_slug")
            if lifecycle_slug and lifecycle_slug in lifecycle_map:
                kwargs["lifecycle_status_id"] = lifecycle_map[lifecycle_slug].id

            # Spread creation dates over last 45 days (deterministic by index)
            days_ago = 2 + (idx * 47 % 43)  # Pseudo-spread without randomness
            kwargs["created_at"] = datetime.now(timezone.utc) - timedelta(days=days_ago)

            idea, created = create_idea_if_not_exists(
                db, tmpl["title"], product.id, **kwargs
            )

            # Track the AI OCR idea as the duplicate target
            if tmpl["title"] == "AI-Powered Invoice Data Extraction from PDF Attachments":
                duplicate_target = idea

            # Set duplicate_of for duplicate ideas
            if tmpl["status"] == IdeaStatus.DUPLICATE and duplicate_target:
                idea.duplicate_of_idea_id = duplicate_target.id
                idea.similarity_score = tmpl.get("similarity", 0.85)

            idea_objects.append((idea, tmpl, created))
            if created:
                ideas_created += 1

        db.commit()
        print(f"  {ideas_created} new ideas created, {len(AP_AUTOMATION_IDEAS) - ideas_created} already existed")

        # --- Votes ---
        print("Creating votes...")
        votes_created = 0

        vote_tiers = {
            "hot": (8, 12),
            "moderate": (3, 7),
            "low": (1, 3),
            "none": (0, 0),
        }

        for idea_idx, (idea, tmpl, is_new) in enumerate(idea_objects):
            if not is_new:
                continue
            tier = tmpl.get("vote_tier", "none")
            min_votes, max_votes = vote_tiers[tier]
            if max_votes == 0:
                continue

            # Deterministic vote count based on idea index
            num_votes = min_votes + (idea_idx * 3 % (max_votes - min_votes + 1))
            # Select first N voters (deterministic)
            selected_voters = voter_users[:num_votes]

            for voter in selected_voters:
                if add_vote_if_not_exists(db, idea.id, voter.id):
                    votes_created += 1

        db.commit()
        print(f"  {votes_created} votes created")

        # --- Comments ---
        print("Creating comments...")
        comments_created = 0

        for idea, tmpl, is_new in idea_objects:
            if not is_new:
                continue
            # PO comments on accepted ideas with lifecycle status
            if tmpl["status"] == IdeaStatus.ACCEPTED and tmpl.get("lifecycle_slug"):
                slug = tmpl["lifecycle_slug"]
                if slug == "delivered":
                    add_comment(db, idea.id, po_user.id,
                                "This has been implemented and is available in the latest release. Thanks to everyone who voted for this!")
                    comments_created += 1
                elif slug == "in_development":
                    add_comment(db, idea.id, po_user.id,
                                "Great news — engineering has picked this up. Targeting release in the next sprint cycle.")
                    comments_created += 1
                elif slug == "on_roadmap":
                    add_comment(db, idea.id, po_user.id,
                                "We've prioritized this based on customer demand. Planning to start development in Q2.")
                    comments_created += 1

            # Voter discussion on hot ideas
            if tmpl.get("vote_tier") == "hot":
                add_comment(db, idea.id, voter_users[0].id,
                            "This would be a huge time-saver for our team. We process 200+ invoices a week and this pain point comes up constantly.")
                comments_created += 1

            # System comments on duplicate ideas
            if tmpl["status"] == IdeaStatus.DUPLICATE and duplicate_target:
                add_comment(db, idea.id, admin_user.id,
                            f"This idea has been identified as similar to \"{duplicate_target.title}\" (similarity: {tmpl.get('similarity', 0.85):.0%}). Votes have been consolidated.",
                            is_system=True)
                comments_created += 1

            # Auto-response on feature_exists
            if tmpl["status"] == IdeaStatus.FEATURE_EXISTS:
                idea.auto_response_text = "Thanks for the suggestion! This feature already exists in Concur Invoice as 'Email Invoice Capture'. You can configure it under Settings > Invoice Sources > Email Capture."
                add_comment(db, idea.id, admin_user.id,
                            "This feature already exists. See auto-response for details.",
                            is_system=True)
                comments_created += 1

        db.commit()
        print(f"  {comments_created} comments created")

        # --- Status History ---
        print("Creating status history...")
        history_created = 0

        for idea, tmpl, is_new in idea_objects:
            if not is_new:
                continue
            # Initial submission
            add_status_history(
                db, idea.id, None, IdeaStatus.PENDING,
                user_id=idea.submitter_id,
                is_automated=False,
                source="submission",
            )
            history_created += 1

            # Triage transition for non-pending ideas
            if tmpl["status"] != IdeaStatus.PENDING:
                triage = tmpl.get("triage", {})
                confidence_pct = int((triage.get("confidence", 0.8)) * 100) if triage else 80

                if tmpl["status"] == IdeaStatus.ACCEPTED:
                    # AI triage recommended accept
                    add_status_history(
                        db, idea.id, IdeaStatus.PENDING, IdeaStatus.ACCEPTED,
                        is_automated=True,
                        source="agent_triage",
                        comment="Automated triage: accepted based on relevance and customer demand signal.",
                        confidence=confidence_pct,
                    )
                    history_created += 1

                    # PO review confirmation
                    add_status_history(
                        db, idea.id, IdeaStatus.ACCEPTED, IdeaStatus.ACCEPTED,
                        user_id=po_user.id,
                        is_automated=False,
                        source="po_response",
                        comment="Confirmed acceptance.",
                    )
                    history_created += 1

                elif tmpl["status"] == IdeaStatus.NEEDS_REVIEW:
                    add_status_history(
                        db, idea.id, IdeaStatus.PENDING, IdeaStatus.NEEDS_REVIEW,
                        is_automated=True,
                        source="agent_triage",
                        comment=triage.get("reasoning", "Flagged for manual review."),
                        confidence=confidence_pct,
                    )
                    history_created += 1

                elif tmpl["status"] == IdeaStatus.DUPLICATE:
                    add_status_history(
                        db, idea.id, IdeaStatus.PENDING, IdeaStatus.DUPLICATE,
                        is_automated=True,
                        source="agent_triage",
                        comment=f"Detected as duplicate (similarity: {tmpl.get('similarity', 0.85):.0%}).",
                        confidence=89,
                    )
                    history_created += 1

                elif tmpl["status"] == IdeaStatus.FEATURE_EXISTS:
                    add_status_history(
                        db, idea.id, IdeaStatus.PENDING, IdeaStatus.FEATURE_EXISTS,
                        is_automated=True,
                        source="agent_triage",
                        comment="Feature already exists in the product.",
                        confidence=92,
                    )
                    history_created += 1

        db.commit()
        print(f"  {history_created} status history entries created")

        # --- Summary ---
        print()
        print("=" * 60)
        print("Demo data seeding complete!")
        print("=" * 60)
        print()
        print(f"Product:           {product.product_name} (ID={product.id})")
        print(f"Users:             {len(DEMO_USERS)} (password: '{DEMO_PASSWORD}')")
        print(f"Permissions:       2 POs (ADMIN), 12 voters (VIEW)")
        print(f"Lifecycle stages:  {len(LIFECYCLE_STATUSES)}")
        print(f"Ideas:             {len(AP_AUTOMATION_IDEAS)}")
        print()
        print("Demo accounts:")
        print(f"  Admin:   demo_admin / {DEMO_PASSWORD}")
        print(f"  PO:      demo_po_1 / {DEMO_PASSWORD}")
        print(f"  PO:      demo_po_2 / {DEMO_PASSWORD}")
        print(f"  Voter:   voter_01 / {DEMO_PASSWORD}")
        print()
        print("Cleanup: ./venv/bin/python -m scripts.seed_demo_data --cleanup")
        print()

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


def cleanup():
    """Remove all seed data (users, permissions, ideas, votes, comments, history)."""
    db = SessionLocal()
    try:
        # Find seed users by email domain
        seed_users = db.query(User).filter(
            User.email.like(f"%{SEED_EMAIL_DOMAIN}")
        ).all()
        seed_user_ids = [u.id for u in seed_users]

        if not seed_user_ids:
            print("No seed data found. Nothing to clean up.")
            return

        # Find seed ideas by title
        seed_titles = [tmpl["title"] for tmpl in AP_AUTOMATION_IDEAS]
        seed_ideas = db.query(Idea).filter(Idea.title.in_(seed_titles)).all()
        seed_idea_ids = [i.id for i in seed_ideas]

        # Delete in dependency order
        if seed_idea_ids:
            deleted = db.query(IdeaComment).filter(
                IdeaComment.idea_id.in_(seed_idea_ids)
            ).delete(synchronize_session=False)
            print(f"  Deleted {deleted} comments")

            deleted = db.query(IdeaStatusHistory).filter(
                IdeaStatusHistory.idea_id.in_(seed_idea_ids)
            ).delete(synchronize_session=False)
            print(f"  Deleted {deleted} status history entries")

            deleted = db.query(Vote).filter(
                Vote.idea_id.in_(seed_idea_ids)
            ).delete(synchronize_session=False)
            print(f"  Deleted {deleted} votes")

            deleted = db.query(Idea).filter(
                Idea.id.in_(seed_idea_ids)
            ).delete(synchronize_session=False)
            print(f"  Deleted {deleted} ideas")

        # Delete permissions granted to seed users
        deleted = db.query(ProductPermission).filter(
            ProductPermission.user_id.in_(seed_user_ids)
        ).delete(synchronize_session=False)
        print(f"  Deleted {deleted} product permissions")

        # Delete seed users
        deleted = db.query(User).filter(
            User.id.in_(seed_user_ids)
        ).delete(synchronize_session=False)
        print(f"  Deleted {deleted} users")

        # Delete demo product if it was created by a seed admin
        # and has no non-seed ideas remaining
        demo_product = db.query(CIProduct).filter(
            CIProduct.product_name == DEMO_PRODUCT["product_name"]
        ).first()
        if demo_product:
            remaining_ideas = db.query(Idea).filter(
                Idea.product_id == demo_product.id
            ).count()
            if remaining_ideas == 0:
                db.delete(demo_product)
                print(f"  Deleted demo product: {demo_product.product_name}")
            else:
                print(f"  Kept product '{demo_product.product_name}' ({remaining_ideas} non-seed ideas remain)")

        db.commit()
        print()
        print("Cleanup complete.")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if "--cleanup" in sys.argv:
        print("Cleaning up seed data...")
        print()
        cleanup()
    else:
        seed()
