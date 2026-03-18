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
        "triage": {
            "confidence": 0.94,
            "reasoning": "Strong product-market fit with clear ROI. Slack is the dominant workplace messaging platform and invoice approval delays are a top-3 customer pain point. Multiple enterprise customers have requested this in the last two quarters. Implementation leverages existing Slack API patterns from our expense module.",
            "recommendation": "accept",
        },
        "jtbd": "When I have invoices approaching their approval deadline, I want to receive actionable alerts in the tool I already use for work, so I can avoid late payment penalties and capture early-pay discounts.",
        "auto_response": "Thank you for this suggestion! We agree that bringing invoice approvals into Slack would significantly reduce missed deadlines. This idea has been accepted and is currently in development. We're targeting availability in the next release cycle.",
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
        "triage": {
            "confidence": 0.91,
            "reasoning": "High strategic value — bridges the gap between AP operations and treasury planning. No direct competitor offers predictive cash flow from the AP pipeline. The data already exists in our system (pending invoices, approval velocity, payment terms); this is primarily a visualization and ML modeling effort. Strong signal from CFO-level stakeholders at 3 enterprise accounts.",
            "recommendation": "accept",
        },
        "jtbd": "When I'm planning cash allocations for the coming weeks, I want to see projected AP outflows based on our actual invoice pipeline, so I can make accurate cash positioning decisions without manually aggregating data from multiple systems.",
        "auto_response": "Great idea! Predictive cash flow visibility is a gap we've heard about from multiple finance teams. This has been accepted and added to our roadmap for Q2 development. We'll be reaching out to interested customers for early feedback sessions.",
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
        "triage": {
            "confidence": 0.96,
            "reasoning": "Core capability gap — competitors Stampli, Tipalti, and Bill.com all offer AI-powered invoice data extraction. Manual PDF data entry is consistently ranked as the #1 time sink by AP teams in our user research. Modern LLM-based extraction achieves 95%+ accuracy on structured invoices, making this technically feasible with high confidence. Critical for competitive positioning.",
            "recommendation": "accept",
        },
        "jtbd": "When I receive a batch of vendor invoices as PDF attachments, I want the system to automatically extract all relevant data fields, so I can eliminate manual data entry and process invoices in minutes instead of hours.",
        "auto_response": "This is one of our most-requested features! AI-powered invoice extraction is now in active development. Our initial testing shows 95%+ accuracy on standard invoice formats. We'll be rolling this out in phases, starting with header-level extraction and adding line-item support shortly after.",
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
        "triage": {
            "confidence": 0.87,
            "reasoning": "Well-scoped UX improvement with clear time savings. The risk threshold concept is sound — PO-matched invoices from known vendors under a configurable amount represent genuinely low-risk approvals. Audit trail requirements are straightforward. Main consideration is ensuring the batch action doesn't circumvent compliance controls.",
            "recommendation": "accept",
        },
        "jtbd": "When I have a queue of routine, low-risk invoices waiting for my approval, I want to approve them all at once with a single action, so I can focus my review time on high-value or exception invoices.",
        "auto_response": "Thanks for the suggestion! We agree that batch approval for low-risk invoices would save significant time. This has been accepted and is on our roadmap. We're designing it with configurable risk thresholds so your organization can set the right guardrails.",
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
        "triage": {
            "confidence": 0.83,
            "reasoning": "Addresses a real pain point for NetSuite customers. GL code drift between systems is a common source of month-end reconciliation issues. Two-way sync is technically achievable via NetSuite's SuiteTalk API. Moderate implementation effort — requires webhook listeners and conflict resolution logic. Good fit for our ERP integration roadmap.",
            "recommendation": "accept",
        },
        "jtbd": "When GL codes are added or updated in our ERP system, I want them to automatically sync to our invoice platform, so I can avoid coding errors and month-end reconciliation delays caused by stale code lists.",
        "auto_response": "Thank you for this request! GL code synchronization with NetSuite is a common pain point we've heard about. This idea has been accepted and will be part of our deeper NetSuite integration effort.",
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
        "triage": {
            "confidence": 0.85,
            "reasoning": "High-impact feature for AP team productivity. Vendor payment inquiries are a significant time drain — industry benchmarks suggest 20-30% of AP team time goes to status calls. A self-service portal directly addresses this. Competitors like Tipalti and Bill.com already offer vendor portals. Moderate complexity — requires vendor authentication, role-based access, and real-time status exposure.",
            "recommendation": "accept",
        },
        "jtbd": "When I need to know the status of an invoice I submitted, I want to look it up myself in a portal, so I can get an immediate answer without waiting for the AP team to respond to my inquiry.",
        "auto_response": "This is a great suggestion that would benefit both vendors and AP teams. We've accepted this idea and will be designing a vendor-facing portal with real-time invoice status tracking.",
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
        "triage": {
            "confidence": 0.90,
            "reasoning": "Direct competitive gap — Stampli already offers AI-powered duplicate detection as a differentiator. Duplicate payments are a measurable cost center (0.1-0.5% of AP spend). Fuzzy matching on vendor name + amount + date is well-understood technically. This is both a competitive response and a clear value-add. Sourced from competitive intelligence on Stampli's feature set.",
            "recommendation": "accept",
        },
        "jtbd": "When I'm processing an invoice that might be a resubmission, I want the system to automatically flag potential duplicates even when formatting differs, so I can prevent duplicate payments that cost the company money.",
        "auto_response": "Duplicate detection is a critical AP safeguard. We've accepted this idea and are building fuzzy matching capabilities that go beyond exact invoice number matching to catch near-duplicates by vendor, amount, and date.",
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
        "triage": {
            "confidence": 0.82,
            "reasoning": "Natural extension of our mobile capabilities. Concur already has strong mobile receipt capture for expenses — extending this to invoices with PO matching leverages existing infrastructure. Addresses the paper invoice gap for field teams. Moderate effort since OCR pipeline exists; main work is PO matching logic and AP workflow integration.",
            "recommendation": "accept",
        },
        "jtbd": "When I receive a paper invoice while traveling or in the field, I want to capture it immediately from my phone and have it matched to the right PO, so I can ensure it enters the AP workflow without delay or risk of being lost.",
        "auto_response": "Thanks for the suggestion! Mobile invoice capture is a natural extension of our existing receipt capture capabilities. This idea has been accepted and we'll be integrating it with PO matching for seamless field-to-AP workflows.",
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
        "triage": {
            "confidence": 0.93,
            "reasoning": "High-demand feature addressing a fundamental workflow limitation. Configurable approval routing by invoice attributes is table stakes for enterprise AP platforms. Currently our single-chain approach is a common objection in sales cycles. Rule-based routing engine is well-understood architecturally. Strong customer demand signal across multiple segments.",
            "recommendation": "accept",
        },
        "jtbd": "When different types of invoices require different levels of review, I want to define approval rules based on invoice attributes, so I can route each invoice to the right approvers without manual intervention or unnecessary bottlenecks.",
        "auto_response": "Great news — configurable approval workflows by invoice type have been built and are now available! You can set up routing rules based on vendor category, amount thresholds, cost center, and GL code under Settings > Approval Workflows.",
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
        "triage": {
            "confidence": 0.79,
            "reasoning": "Useful operational reporting feature. Three-way match rate is a key AP KPI but currently requires manual Excel analysis. Scheduled report delivery is a standard pattern. Lower urgency than core workflow features but solid value for AP managers. Data is readily available — primarily a reporting/visualization effort.",
            "recommendation": "accept",
        },
        "jtbd": "When I need to assess my team's invoice processing efficiency, I want to receive automated reports on three-way match rates and exception patterns, so I can identify problematic vendors and process gaps without manual data analysis.",
        "auto_response": "Thank you for this suggestion! Three-way matching visibility is an important operational metric. This idea has been accepted and we'll be building automated reporting with drill-down capabilities.",
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
        "triage": {
            "confidence": 0.81,
            "reasoning": "Essential for enterprise integration workflows. Programmatic invoice submission is a prerequisite for customers with multiple ERPs or high-volume AP operations. REST API patterns are well-established. Enables a whole class of automation use cases. Aligns with our API-first strategy.",
            "recommendation": "accept",
        },
        "jtbd": "When our ERP system records a new vendor invoice, I want it to be automatically submitted to our AP platform via API, so I can eliminate manual upload steps and reduce invoice processing latency from hours to seconds.",
        "auto_response": "API-based invoice submission is a key enabler for enterprise integration. This idea has been accepted and will be part of our API expansion. We'll publish OpenAPI specs and provide SDKs for major ERP platforms.",
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
        "triage": {
            "confidence": 0.77,
            "reasoning": "Valuable analytics feature sourced from CRM (Salesforce account: Global Logistics Corp). Spend analytics by category and region is a common procurement need but currently requires BI tool export. Our AP data is rich enough to power this natively. Lower priority than core AP workflow features but strong value for procurement stakeholders. Builds on invoice data we already capture.",
            "recommendation": "accept",
        },
        "jtbd": "When I'm preparing for vendor negotiations or evaluating consolidation opportunities, I want to see spend patterns broken down by category and region, so I can identify where we have fragmented spend and negotiate better terms with concentrated volume.",
        "auto_response": "Thank you for this suggestion via your Salesforce feedback! Supplier spend analytics is a natural extension of the invoice data we already capture. This idea has been accepted and we'll be building interactive spend dashboards with category and regional breakdowns.",
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
            "reasoning": "This is a well-defined feature request addressing a clear pain point in multi-currency AP processing. The use case is specific and the value proposition is quantifiable. Real-time exchange rate APIs (ECB, OpenExchangeRates) are reliable and inexpensive. The 2% variance threshold for flagging discrepancies is a sensible default. Recommend acceptance.",
            "recommendation": "accept",
        },
        "jtbd": "When I receive invoices in foreign currencies, I want them automatically converted to our base currency at current exchange rates, so I can process them without manual rate lookups and reduce conversion errors.",
        "auto_response": "Thank you for this suggestion! Automated currency conversion would streamline multi-currency invoice processing significantly. We're evaluating this for our international AP capabilities roadmap.",
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
            "reasoning": "Reasonable feature request for vendor management. The implementation scope is moderate — requires a vendor tiering system and term inheritance logic. Some overlap with existing vendor management features. The tiering concept adds value but may require careful UX design to avoid over-complicating vendor setup for smaller organizations.",
            "recommendation": "accept",
        },
        "jtbd": "When a new invoice arrives from a vendor with negotiated payment terms, I want the correct terms applied automatically based on vendor tier, so I can avoid manual entry errors that lead to missed discounts or late fees.",
        "auto_response": "Thanks for the idea! Configurable payment term defaults by vendor tier would reduce manual entry and help ensure negotiated terms are consistently applied. We're reviewing this for our vendor management improvements.",
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
            "reasoning": "This is a strategic integration request with significant competitive implications. Coupa is a direct competitor in the AP space — integrating with them could legitimize their platform as the procurement layer while positioning us as the AP layer, or it could be seen as acknowledging their procurement dominance. Needs product strategy review to assess partnership vs. competition dynamics before acceptance.",
            "recommendation": "review",
        },
        "jtbd": "When we use separate platforms for procurement and AP, I want end-to-end visibility from purchase requisition through invoice payment, so I can track the full procure-to-pay lifecycle without switching between systems.",
        "auto_response": "Thank you for this suggestion. A Coupa integration raises important strategic questions about our positioning in the procure-to-pay workflow. We're reviewing this with our product strategy team.",
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
            "reasoning": "While audit trail integrity is important, blockchain may be over-engineered for this use case. Existing database audit logs with proper access controls and write-once storage (e.g., append-only tables, immutable cloud storage) achieve similar tamper-resistance at much lower complexity and cost. No competitors in the AP space have adopted blockchain for audit trails. The ROI is questionable given implementation and operational overhead. Flagged for PM review.",
            "recommendation": "review",
        },
        "jtbd": "When auditors need to verify the integrity of our invoice processing history, I want tamper-proof records of every submission and approval, so I can demonstrate compliance with confidence that no records have been altered.",
        "auto_response": "Thank you for raising audit trail integrity. While this is an important concern, we'd like to explore whether existing database audit mechanisms with proper access controls might address this need more efficiently than blockchain. We're reviewing the best approach.",
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
            "reasoning": "Novel idea but raises significant security and privacy concerns — voice assistants in shared office environments could inadvertently expose sensitive financial data (invoice amounts, vendor names, approval queues). The use case is niche; AP managers rarely need hands-free access and mobile app provides on-the-go access already. Low customer demand signal — only one support ticket. Flagged for PM review due to security implications.",
            "recommendation": "review",
        },
        "jtbd": "When I'm away from my desk and need a quick status update on my approval queue, I want to ask a voice assistant for invoice summaries, so I can stay informed without needing to open my laptop or phone.",
        "auto_response": "Thanks for this creative suggestion! Voice-activated access to AP data is an interesting idea, though we'd need to carefully evaluate the security implications of exposing financial data through voice assistants in shared environments. We're reviewing this with our security team.",
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
        "triage": {
            "confidence": 0.89,
            "reasoning": "This idea is substantially similar to the existing 'AI-Powered Invoice Data Extraction from PDF Attachments' idea (89% semantic similarity). Both describe ML/AI-based extraction of invoice data from PDF documents. The existing idea is more detailed with specific implementation scope. Votes and discussion should be consolidated under the original idea.",
            "recommendation": "duplicate",
        },
        "jtbd": "When I have a stack of invoice PDFs, I want the system to automatically read and populate all fields using ML, so I can eliminate manual data entry and reduce processing errors.",
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
            "reasoning": "This feature already exists in Concur Invoice as 'Email Invoice Capture'. The submitter may not be aware of the existing functionality. The feature is available under Settings > Invoice Sources > Email Capture and supports automatic attachment ingestion and invoice record creation. Auto-response recommended with documentation link.",
            "recommendation": "feature_exists",
        },
        "jtbd": "When my vendors want to submit invoices without using a portal, I want them to be able to email invoices to a dedicated address, so I can receive them digitally without requiring vendor portal adoption.",
        "auto_response": "Thanks for the suggestion! This feature already exists in Concur Invoice as 'Email Invoice Capture'. You can configure it under Settings > Invoice Sources > Email Capture. Vendors can email invoice PDFs to your dedicated AP address and the system will automatically ingest the attachment and create an invoice record.",
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

            # JTBD statement
            if tmpl.get("jtbd"):
                kwargs["jtbd_statement"] = tmpl["jtbd"]

            # Auto-response text
            if tmpl.get("auto_response"):
                kwargs["auto_response_text"] = tmpl["auto_response"]

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
        print(f"Permissions:       2 POs (OWNER), 12 voters (VIEW)")
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
    from app.models.pm_review import PMReviewQueue
    from app.models.product_invite import ProductInviteCode
    from app.models.cost_tracking import LLMUsageLog
    from app.models.queue import QueueJob

    db = SessionLocal()
    try:
        # Disable FK checks during cleanup to avoid ordering issues
        # (many tables cross-reference seed users)
        from sqlalchemy import text
        db.execute(text("PRAGMA foreign_keys = OFF"))

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

        # Clean up ancillary tables referencing seed users
        for model, col_name in [
            (ProductInviteCode, "created_by_user_id"),
            (QueueJob, "user_id"),
            (LLMUsageLog, "user_id"),
        ]:
            col = getattr(model, col_name)
            deleted = db.query(model).filter(
                col.in_(seed_user_ids)
            ).delete(synchronize_session=False)
            if deleted:
                print(f"  Deleted {deleted} {model.__tablename__} entries")

        # Delete in dependency order
        if seed_idea_ids:
            deleted = db.query(PMReviewQueue).filter(
                PMReviewQueue.item_type == "idea",
                PMReviewQueue.item_id.in_(seed_idea_ids)
            ).delete(synchronize_session=False)
            if deleted:
                print(f"  Deleted {deleted} review queue entries")

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

        # Delete all permissions on the demo product (includes granted_by refs to seed users)
        demo_product = db.query(CIProduct).filter(
            CIProduct.product_name == DEMO_PRODUCT["product_name"]
        ).first()

        if demo_product:
            demo_product_id = demo_product.id
            db.expunge(demo_product)  # Detach to avoid ORM cascade

            deleted = db.query(ProductPermission).filter(
                ProductPermission.product_id == demo_product_id
            ).delete(synchronize_session=False)
            print(f"  Deleted {deleted} product permissions")

            # Delete demo product before users (product references created_by_user_id)
            # Use query delete to avoid ORM cascade nullifying related tables
            remaining_ideas = db.query(Idea).filter(
                Idea.product_id == demo_product_id
            ).count()
            if remaining_ideas == 0:
                db.query(CIProduct).filter(
                    CIProduct.id == demo_product_id
                ).delete(synchronize_session=False)
                print(f"  Deleted demo product: {DEMO_PRODUCT['product_name']}")
            else:
                print(f"  Kept product '{DEMO_PRODUCT['product_name']}' ({remaining_ideas} non-seed ideas remain)")
        else:
            # Still clean up permissions for seed users on any product
            deleted = db.query(ProductPermission).filter(
                ProductPermission.user_id.in_(seed_user_ids)
            ).delete(synchronize_session=False)
            print(f"  Deleted {deleted} product permissions")

        # Delete seed users (after product and permissions are gone)
        deleted = db.query(User).filter(
            User.id.in_(seed_user_ids)
        ).delete(synchronize_session=False)
        print(f"  Deleted {deleted} users")

        db.commit()
        db.execute(text("PRAGMA foreign_keys = ON"))
        print()
        print("Cleanup complete.")

    except Exception as e:
        db.rollback()
        db.execute(text("PRAGMA foreign_keys = ON"))
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
