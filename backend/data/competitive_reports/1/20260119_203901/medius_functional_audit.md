# Functional Audit: Medius

## 0. Competitor Context

**Positioning:** Medius positions itself as a comprehensive Source-to-Pay (S2P) platform that goes beyond traditional AP automation to manage the entire spend lifecycle from sourcing through payment, with emphasis on autonomous invoice processing and spend control.

**Core Differentiation:** Full Source-to-Pay suite integration combining procurement, AP automation, and payment optimization with AI-powered autonomous processing and strong focus on supplier management and early payment programs for working capital optimization.

**Target Customer:** Mid-market to enterprise organizations seeking end-to-end spend management, particularly those wanting to consolidate procurement and AP processes, with emphasis on manufacturing, healthcare, and professional services sectors.

**Key Features:**
- Autonomous invoice processing with AI
- Complete Source-to-Pay platform integration
- Dynamic discounting and early payment programs
- Supplier collaboration portal
- Advanced spend analytics and forecasting

## 1. Functional Comparison Table

| Feature Category | Competitor Feature | Description | Status |
|-----------------|-------------------|-------------|--------|
| Invoice Processing | Autonomous Invoice Processing | AI-driven touchless invoice processing that learns from patterns to auto-code, route, and approve invoices without human intervention for matching invoices. | **Differentiator** |
| Invoice Processing | Invoice Capture and OCR | Automated data extraction from invoices in multiple formats including email, PDF, EDI, and paper with validation. | **Parity** |
| Procurement | Integrated Source-to-Pay Platform | Native procurement module covering sourcing, contracts, catalogs, and purchase requisitions within the same platform as AP. | **Gap** |
| Procurement | Supplier Onboarding and Portal | Self-service supplier portal for registration, document submission, invoice status tracking, and communication. | **Gap** |
| Approval Workflows | Configurable Approval Workflows | Multi-level approval routing based on amount, department, GL code, or custom rules with delegation capabilities. | **Parity** |
| Matching | Two-Way and Three-Way Matching | Automated matching of invoices to POs and receipts with configurable tolerance thresholds and exception handling. | **Parity** |
| Payment Optimization | Dynamic Discounting | Automated early payment discount capture with configurable rules based on cash position and discount rates. | **Gap** |
| Payment Optimization | Supply Chain Finance Programs | Embedded supplier financing options allowing suppliers to receive early payment while buyer maintains payment terms. | **Gap** |
| Payment Processing | Multi-Currency Payment Processing | Native support for global payments in multiple currencies with FX rate management and international payment formats. | **Parity** |
| Analytics | Spend Analytics and Forecasting | Real-time dashboards showing spend by category, supplier, department with predictive cash flow forecasting and budget tracking. | **Gap** |
| Analytics | Supplier Performance Management | Scorecarding and KPI tracking for supplier quality, delivery, compliance, and financial health monitoring. | **Gap** |
| Compliance | Policy Enforcement and Audit Trail | Automated policy checks with complete audit trail for all transactions and approval decisions. | **Parity** |
| Fraud Prevention | Duplicate Detection and Prevention | Automated duplicate invoice detection across multiple dimensions including invoice number, amount, vendor, and date. | **Parity** |
| Integration | ERP Integration Hub | Pre-built connectors for major ERPs including SAP, Oracle, NetSuite, Microsoft Dynamics with bi-directional data sync. | **Parity** |
| Contract Management | Contract Lifecycle Management | Contract repository with automated renewals, obligation tracking, and linkage to invoices for compliance verification. | **Gap** |

## 2. Deep-Dive on Gaps

### Autonomous Invoice Processing

**User Problem:** AP teams spend excessive time on manual invoice coding and routing, even with basic automation, creating bottlenecks for high-volume environments.

**Evidence:** Medius claims 'autonomous AP' that learns organizational patterns to automatically code and route invoices without rules configuration, reducing touchpoints by up to 80% for matching invoices.

### Integrated Source-to-Pay Platform

**User Problem:** Organizations using separate procurement and AP systems face data synchronization issues, duplicate vendor records, and inability to track spend from requisition through payment.

**Evidence:** Medius provides native procurement functionality within the same platform, eliminating integration complexity and providing unified spend visibility across the entire purchase-to-pay cycle.

### Supplier Collaboration Portal

**User Problem:** AP teams field constant supplier inquiries about invoice status and payment timing, consuming significant staff time and creating supplier friction.

**Evidence:** Medius offers a self-service portal where suppliers can check invoice status, upload documents, and communicate directly, reducing AP inquiry volume by 60-70% according to their case studies.

### Dynamic Discounting

**User Problem:** Organizations miss early payment discount opportunities due to manual processes and lack of visibility into available cash versus discount value.

**Evidence:** Medius automates discount capture by analyzing cash position and discount rates in real-time, automatically flagging and processing early payments when ROI exceeds threshold, capturing 2-3% annual savings.

### Supply Chain Finance Programs

**User Problem:** Buyers want extended payment terms for cash flow but suppliers need faster payment, creating tension in supplier relationships and limiting negotiation leverage.

**Evidence:** Medius embeds supply chain finance allowing suppliers to receive early payment from third-party financiers while buyers maintain extended terms, improving supplier relationships and negotiating power.

### Spend Analytics and Forecasting

**User Problem:** Finance teams lack forward-looking visibility into upcoming liabilities and cannot accurately forecast cash requirements or identify spend optimization opportunities.

**Evidence:** Medius provides predictive cash flow forecasting based on invoice pipeline, payment terms, and historical patterns, plus category spend analysis to identify consolidation and negotiation opportunities.

### Supplier Performance Management

**User Problem:** Organizations cannot systematically track supplier quality, delivery, and compliance issues, making vendor rationalization and sourcing decisions subjective.

**Evidence:** Medius scorecards suppliers across quality, delivery, compliance, and financial metrics with automated data collection from invoices and receipts, enabling data-driven supplier decisions.

### Contract Lifecycle Management

**User Problem:** Contracts exist in disparate systems or file shares with no linkage to invoices, making it impossible to verify pricing compliance or prevent missed renewals.

**Evidence:** Medius links contracts to invoices for automated price verification, tracks renewal dates with alerts, and monitors obligation fulfillment, preventing revenue leakage and unfavorable auto-renewals.

## 3. Technical Constraints

**Integrations:** SAP S/4HANA and ECC, Oracle ERP Cloud and E-Business Suite, Microsoft Dynamics 365 and AX, NetSuite, Workday, Infor, IFS, Epicor, Banking platforms for payment file generation, Procurement systems via API

**API Capabilities:** RESTful API for custom integrations, supplier portal API for external vendor systems, webhook support for real-time event notifications, and bulk data import/export capabilities.

**Platform Requirements:** Cloud-based SaaS platform with no on-premise requirements, browser-based access, mobile app for approvals on iOS and Android, supports SSO via SAML 2.0 and OAuth.

**Additional Notes:** Medius emphasizes their platform approach versus point solutions, positioning as a single system of record for all spend. Strong focus on European market with multi-language and regulatory compliance. Offers managed services for invoice processing as an alternative to pure software.
