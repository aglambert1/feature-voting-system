/**
 * Shared TypeScript type definitions
 *
 * These types match the backend Pydantic schemas and database models.
 */

// ============================================================================
// ENUMS
// ============================================================================

export enum UserRole {
  ADMIN = 'admin',
  VOTER = 'voter',
  PRODUCT_OWNER = 'product_owner',
}

export enum SourceType {
  CUSTOMER_SUBMISSION = 'customer_submission',
  COMPETITOR_AUTOMATED = 'competitor_automated',
  CRM_IMPORT = 'crm_import',
  SUPPORT_TICKET = 'support_ticket',
}

/**
 * Unified idea status.
 * Each status has a deterministic is_active value (configurable per-product).
 */
export enum IdeaStatus {
  PENDING = 'pending',           // is_active=false - awaiting triage
  ACCEPTED = 'accepted',         // is_active=true  - approved for voting
  NEEDS_REVIEW = 'needs_review', // is_active=false - awaiting PO
  DUPLICATE = 'duplicate',       // is_active=false - matches existing idea
  MERGED = 'merged',             // is_active=false - combined with another (future)
  FEATURE_EXISTS = 'feature_exists',  // is_active=false - already in product
  NOT_APPROPRIATE = 'not_appropriate', // is_active=false - rejected
}

// ============================================================================
// AUTH TYPES
// ============================================================================

export interface User {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterData {
  email: string;
  username: string;
  password: string;
  full_name?: string;
  role?: UserRole;
  invite_code?: string;
  product_ids?: number[];
}

export interface InviteCodeInfo {
  valid: boolean;
  product_name?: string;
  message: string;
}

export interface InviteCode {
  id: number;
  product_id: number;
  code: string;
  invite_url: string;
  max_uses: number | null;
  current_uses: number;
  permission_level: string;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ProductMember {
  user_id: number;
  username: string;
  email: string;
  permission_level: string;
  granted_at: string;
}

export interface UserProduct {
  product_id: number;
  product_name: string;
  permission_level: string;
  granted_at: string;
}

export interface AuthResult {
  success: boolean;
  error?: string;
}

// ============================================================================
// IDEA TYPES
// ============================================================================

export interface VoteCount {
  upvotes: number;
  total_votes: number;
}

// Sort options for ideas list
export type IdeaSortOption = 'most_votes' | 'pending_first' | 'most_recent' | 'my_ideas';

export interface IdeaListItem {
  id: number;
  title: string;
  what_description: string;
  why_description: string | null;
  use_case_description: string | null;
  category: string | null;
  created_at: string;
  product_id: number;
  product_name: string | null;
  // Status fields
  status: IdeaStatus | null;
  is_active: boolean | null;
  duplicate_of_idea_id: number | null;
  duplicate_of_title: string | null;
  // Lifecycle status (post-acceptance stage)
  lifecycle_status_id: number | null;
  lifecycle_status_name: string | null;
  lifecycle_status_color: string | null;
  // Submitter info
  submitter_id: number | null;
  // Vote counts
  vote_counts: VoteCount;
  user_vote: number | null;
  user_vote_timestamp: string | null;  // Timestamp when user voted
}

export interface IdeaResponse {
  id: number;
  title: string;
  what_description: string;
  why_description: string;
  use_case_description: string;
  category: string | null;
  source_type: SourceType;
  status: IdeaStatus;
  created_at: string;
  updated_at: string;
  product_id: number;
  product_name: string | null;
  vote_counts: VoteCount;
  user_vote: number | null;
}

export interface IdeaListResponse {
  ideas: IdeaListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface IdeaCreate {
  title: string;
  what_description: string;
  why_description: string;
  use_case_description: string;
  category?: string;
  product_id: number;
}

export interface SimilarIdea {
  id: number;
  title: string;
  what_description: string;
  similarity_score: number;
}

// ============================================================================
// SUBMISSION TYPES
// ============================================================================

export interface StructureResponse {
  title: string;
  what: string;
  why: string;
  use_case: string;
  what_description?: string;
  why_description?: string;
  use_case_description?: string;
}

export interface SubmissionData {
  title: string;
  what_description: string;
  why_description: string;
  use_case_description: string;
  product_id: number;
  original_freeform_text?: string;
}

// ============================================================================
// VOTE TYPES
// ============================================================================

export interface VoteResponse {
  vote_counts: VoteCount;
  user_vote: number;
}

// ============================================================================
// PRODUCT TYPES (for Competitor Intelligence)
// ============================================================================

export interface Product {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  user_id: number;
}

export interface ProductCreate {
  name: string;
  description?: string;
}

// ============================================================================
// MULTI-SOURCE PRODUCT TYPES
// ============================================================================

export type ProductSourceType = 'text' | 'document' | 'url';

export interface ProductSource {
  type: ProductSourceType;
  content?: string;           // For text type
  file_id?: string;           // UUID for uploaded documents
  filename?: string;          // Original filename
  extracted_text?: string;    // Parsed text from document/URL
  url?: string;               // URL for url type
  title?: string;             // Page title for URLs
  size_mb?: number;           // File size
  token_estimate?: number;    // Estimated token count
  fetch_timestamp?: string;   // When URL was fetched
}

export interface DocumentUploadResponse {
  file_id: string;
  filename: string;
  file_type: string;
  extracted_text: string;
  size_mb: number;
  token_estimate: number;
}

export interface URLFetchResponse {
  url: string;
  title: string;
  extracted_text: string;
  fetch_timestamp: string;
  token_estimate: number;
}

export interface Competitor {
  id: number;
  product_id: number;
  name: string;
  description: string | null;
  website_url: string | null;
  created_at: string;
}

export interface CompetitorCreate {
  name: string;
  description?: string;
  website_url?: string;
}

export interface Feature {
  id: number;
  product_id: number;
  competitor_id: number | null;
  name: string;
  description: string;
  created_at: string;
}

export interface FeatureCreate {
  name: string;
  description: string;
  competitor_id?: number;
}

export interface AnalysisSession {
  id: number;
  product_id: number;
  stage: number;
  session_data: Record<string, any>;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// API ERROR TYPES
// ============================================================================

export interface ApiError {
  message: string;
  status: number;
  data?: any;
  detail?: string;
}

// ============================================================================
// COMMON UI TYPES
// ============================================================================

export interface SelectOption {
  value: string | number;
  label: string;
}

// ============================================================================
// AXIOS CONFIG EXTENSIONS
// ============================================================================

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipAuthRedirect?: boolean;
  }
}

// ============================================================================
// QUEUE JOB TYPES (Phase 1-4)
// ============================================================================

export enum JobType {
  PRODUCT_ANALYSIS = 'product_analysis',
  COMPETITOR_DISCOVERY = 'competitor_discovery',
  FEATURE_EXTRACTION = 'feature_extraction',
  IDEA_GENERATION = 'idea_generation',
  IDEA_TRIAGE = 'idea_triage',
  COMPETITIVE_MONITORING = 'competitive_monitoring',
  FULL_WORKFLOW = 'full_workflow',
  // V2 competitive analysis
  FUNCTIONAL_AUDIT = 'functional_audit',
  LANDSCAPE_SYNTHESIS = 'landscape_synthesis',
  SCHEDULED_DEEP_ANALYSIS = 'scheduled_deep_analysis',
  // Three-source synthesis
  OPPORTUNITY_SYNTHESIS = 'opportunity_synthesis',
}

export enum JobStatus {
  PENDING = 'pending',
  QUEUED = 'queued',
  RUNNING = 'running',
  SUCCESS = 'success',
  FAILURE = 'failure',
  CANCELLED = 'cancelled',
}

export interface QueueJob {
  id: number;
  job_uuid: string;
  job_type: JobType;
  status: JobStatus;
  progress_percent: number;
  progress_message: string | null;
  input_data: Record<string, any>;
  output_data: Record<string, any> | null;
  error_message: string | null;
  product_id: number | null;
  user_id: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// ============================================================================
// PM REVIEW QUEUE TYPES (Phase 4)
// ============================================================================

export enum ReviewQueueType {
  IDEA = 'idea',
  COMPETITIVE_ALERT = 'competitive_alert',
  REPORT = 'report',
}

export enum ReviewQueueStatus {
  PENDING = 'pending',
  IN_REVIEW = 'in_review',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  DEFERRED = 'deferred',
  DISMISSED = 'dismissed',
}

export enum ReviewQueuePriority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  URGENT = 'urgent',
}

export enum AlertType {
  NEW_COMPETITOR = 'new_competitor',
  COMPETITOR_REMOVED = 'competitor_removed',
  MAJOR_FEATURE_LAUNCH = 'major_feature_launch',
  FEATURE_REMOVED = 'feature_removed',
  PRICING_CHANGE = 'pricing_change',
  TREND_DETECTED = 'trend_detected',
}

export interface PMReviewQueueItem {
  id: number;
  queue_type: ReviewQueueType;
  status: ReviewQueueStatus;
  priority: ReviewQueuePriority;
  item_type: string;
  item_id: number;
  title: string;
  summary: string | null;
  alert_type: AlertType | null;
  alert_severity: 'info' | 'warning' | 'critical' | null;
  metadata: Record<string, any> | null;
  product_id: number;
  assigned_to_user_id: number | null;
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  review_notes: string | null;
  review_action: string | null;
  created_at: string;
  due_by: string | null;
}

export interface PMReviewQueueResponse {
  items: PMReviewQueueItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface PMReviewQueueStats {
  total_pending: number;
  total_in_review: number;
  total_approved: number;
  total_rejected: number;
  by_type: Record<string, number>;
  by_priority: Record<string, number>;
}

// ============================================================================
// MONITORING TYPES (Phase 4)
// ============================================================================

export interface MonitoringConfig {
  id: number;
  product_id: number;
  monitoring_enabled: boolean;
  monitoring_frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly';
  last_monitored_at: string | null;
  next_scheduled_at: string | null;
  alert_on_new_features: boolean;
  alert_on_removed_features: boolean;
  alert_on_new_competitors: boolean;
  min_feature_change_threshold: number;
  auto_generate_ideas: boolean;
  auto_idea_confidence_threshold: number;
  notify_product_owners: boolean;
  notification_settings: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface MonitoringConfigUpdate {
  monitoring_enabled?: boolean;
  monitoring_frequency?: 'daily' | 'weekly' | 'biweekly' | 'monthly';
  alert_on_new_features?: boolean;
  alert_on_removed_features?: boolean;
  alert_on_new_competitors?: boolean;
  min_feature_change_threshold?: number;
  auto_generate_ideas?: boolean;
  auto_idea_confidence_threshold?: number;
  notify_product_owners?: boolean;
}

export interface CompetitorSnapshot {
  id: number;
  product_competitor_id: number;
  competitor_name: string;
  snapshot_date: string;
  feature_count: number;
  features_hash: string;
  has_changes: boolean;
  change_summary: string | null;
  changes_detected: {
    new_features: Array<{ name: string; description: string }>;
    removed_features: Array<{ name: string; id?: number }>;
    modified_features: Array<{ feature: { name: string }; changes: Record<string, any> }>;
    is_new_competitor: boolean;
  } | null;
  alert_generated: boolean;
  alert_type: AlertType | null;
  previous_snapshot_id: number | null;
  created_at: string;
}

export interface CompetitorSnapshotsResponse {
  snapshots: CompetitorSnapshot[];
  total: number;
}

// ============================================================================
// PRODUCT DASHBOARD TYPES
// ============================================================================

export interface ProductListItem {
  id: number;
  product_name: string;
  product_description: string | null;
  product_category: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  pending_ideas_count?: number;
  pending_alerts_count?: number;
  pending_reports_count?: number;
  last_monitored_at?: string | null;
  monitoring_enabled?: boolean;
}

// ============================================================================
// IDEA STATUS ALIASES (for backward compatibility)
// ============================================================================

// TriageStatus is now deprecated - use IdeaStatus instead
// Keeping as alias for any existing code
export const TriageStatus = IdeaStatus;
export type TriageStatusType = IdeaStatus;

// User-facing status for PO response workflow
export type IdeaResponseStatus = 'approved' | 'duplicate' | 'feature_exists' | 'not_appropriate';

// ============================================================================
// IDEA COMMENT TYPES (Plan Phase 2)
// ============================================================================

export interface IdeaComment {
  id: number;
  idea_id: number;
  user_id: number;
  username: string | null;
  comment_text: string;
  is_system_generated: boolean;
  created_at: string;
}

// ============================================================================
// IDEA DETAIL TYPES (Extended for PO workflow)
// ============================================================================

/**
 * Competitive context for ideas generated from competitive analysis.
 * Only visible to PO/Admin users.
 */
export interface CompetitiveContext {
  priority_score: number;
  priority_level: 'critical' | 'high' | 'medium' | 'low';
  competitors_with_feature: string[];
  total_competitors_analyzed: number;
  market_context: string;
  source_evidence_count: number;
  landscape_report_id?: number;
}

export interface IdeaDetail {
  id: number;
  title: string;
  what_description: string;
  why_description: string;
  use_case_description: string;
  source_type: string;
  category: string | null;
  status: IdeaStatus;
  is_active: boolean;
  triage_confidence: number | null;
  triage_recommendation: string | null;
  triage_reasoning: string | null;
  duplicate_of_idea_id: number | null;
  duplicate_of_title: string | null;
  similarity_score: number | null;
  auto_response_text: string | null;
  product_id: number;
  product_name: string | null;
  submitter_id: number | null;
  submitter_username: string | null;
  review_notes: string | null;
  reviewer_username: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  comments: IdeaComment[];
  status_history: StatusHistoryEntry[];
  // Competitive context - only populated for PO/Admin users
  competitive_context: CompetitiveContext | null;
}

// ============================================================================
// IDEA RESPONSE TYPES (PO Workflow)
// ============================================================================

export interface IdeaRespondRequest {
  status: IdeaResponseStatus;
  comment: string;
  duplicate_of_idea_id?: number;
}

export interface IdeaRespondResponse {
  id: number;
  title: string;
  status: IdeaStatus;
  is_active: boolean;
  duplicate_of_idea_id: number | null;
  responded_by: string;
  votes_transferred?: number;  // Only for duplicate responses
}

// ============================================================================
// TRIAGE RECOMMENDATION TYPES (Agent-generated suggestions)
// ============================================================================

export interface SimilarIdeaForTriage {
  id: number;
  title: string;
  similarity_score: number;
}

export interface IdeaVoter {
  id: number;
  username: string;
}

export interface ExistingFeatureMatch {
  feature_name: string;
  feature_description: string;
  similarity_score: number;
  source_url?: string | null;
}

export interface SourceSummary {
  vote_count: number;
  voters: IdeaVoter[];
  competitors_with_feature: string[];
  competitive_urgency: string | null;
  existing_feature: ExistingFeatureMatch | null;
}

export interface CurrentResponse {
  status: IdeaResponseStatus | null;
  comment: string | null;
  reviewed_at: string | null;
}

export interface StatusHistoryEntry {
  id: number;
  previous_status: string | null;
  new_status: string | null;
  changed_by_user_id: number | null;
  changed_by_username: string | null;
  is_automated: boolean;
  change_source: string;  // 'submission', 'agent_triage', 'po_response', 'po_edit'
  comment: string | null;
  confidence: number | null;  // For agent triage, confidence as percentage (0-100)
  created_at: string;
}

export interface TriageRecommendation {
  idea_id: number;
  has_recommendation: boolean;
  recommended_status: IdeaResponseStatus | null;
  confidence: number | null;
  suggested_comment: string | null;
  reasoning: string | null;
  duplicate_of_idea_id: number | null;
  similar_ideas: SimilarIdeaForTriage[];
  source_summary: SourceSummary;
  current_response: CurrentResponse | null;
  status_history: StatusHistoryEntry[];
}

export interface CanRespondResponse {
  idea_id: number;
  can_respond: boolean;
  product_id: number;
}

// ============================================================================
// PRODUCT PENDING COUNTS (Plan Phase 1)
// ============================================================================

export interface ProductPendingCounts {
  product_id: number;
  ideas_pending: number;
  ideas_needs_review: number;  // Used as "auto-responded" in display
  competitive_alerts: number;
}

// ============================================================================
// TRIAGE AUTOMATION SETTINGS (Plan Phase 8)
// ============================================================================

export interface TriageSettings {
  product_id: number;
  auto_enabled: boolean;
  auto_threshold: number;
}

export interface TriageSettingsUpdate {
  auto_enabled: boolean;
  auto_threshold: number;
}

// ============================================================================
// COMPETITIVE AGENT TYPES (Agent-Centric Architecture)
// ============================================================================

/**
 * Agent mode for scheduled vs manual execution.
 */
export enum AgentMode {
  MANUAL = 'manual',
  SCHEDULED = 'scheduled',
}

/**
 * Schedule frequency options.
 */
export type ScheduleFrequency = 'daily' | 'weekly' | 'monthly';

/**
 * Competitive agent configuration for a product.
 */
export interface CompetitiveAgentConfig {
  id: number;
  product_id: number;

  // Product Analysis
  product_analysis_mode: AgentMode | string;
  product_analysis_schedule: ScheduleFrequency | null;
  product_analysis_last_run: string | null;

  // Competitor Discovery
  competitor_discovery_mode: AgentMode | string;
  competitor_discovery_schedule: ScheduleFrequency | null;
  competitor_discovery_last_run: string | null;
  alert_on_new_competitors: boolean;
  alert_on_disappeared_competitors: boolean;

  // Deep Analysis (V2: Functional Audit + Landscape Synthesis)
  deep_analysis_mode: AgentMode | string;
  deep_analysis_schedule: ScheduleFrequency | null;
  deep_analysis_last_run: string | null;

  // Idea Auto-Generation Settings
  intensity_similarity_threshold: number;  // DEPRECATED - kept for backwards compatibility
  intensity_idea_threshold: number;  // Priority score threshold (0.0-1.0)

  enabled: boolean;
}

/**
 * Request to update agent configuration.
 */
export interface CompetitiveAgentConfigUpdate {
  product_analysis_mode?: AgentMode | string;
  product_analysis_schedule?: ScheduleFrequency;

  competitor_discovery_mode?: AgentMode | string;
  competitor_discovery_schedule?: ScheduleFrequency;
  alert_on_new_competitors?: boolean;
  alert_on_disappeared_competitors?: boolean;

  deep_analysis_mode?: AgentMode | string;
  deep_analysis_schedule?: ScheduleFrequency;

  intensity_similarity_threshold?: number;
  intensity_idea_threshold?: number;

  enabled?: boolean;
}

/**
 * Competitor with deep analysis status.
 */
export interface AgentCompetitor {
  id: number;
  product_id: number;
  competitor_name: string;
  competitor_url: string | null;
  status: string;
  deep_analysis_enabled: boolean;
  deep_analysis_status: string | null;
  deep_analysis_last_run: string | null;
  feature_count: number;
  evidence_count: number;
}

/**
 * Competitor feature with cluster info.
 */
export interface CompetitorFeature {
  id: number;
  product_competitor_id: number;
  feature_name: string;
  feature_description: string | null;
  feature_category: string | null;
  status: string;
  cluster_id: number | null;
  cluster_name: string | null;
}

/**
 * Response from triggering an async job.
 */
export interface AgentJobResponse {
  job_id: number;
  job_uuid: string;
  job_type: string;
  status: string;
  message: string;
}

/**
 * Request to create ideas from features.
 */
export interface CreateIdeasRequest {
  feature_ids: number[];
}

// ============================================================================
// FEATURE QUERY TYPES (Chat Interface)
// ============================================================================

/**
 * Request to query if a feature exists in a product.
 */
export interface FeatureQueryRequest {
  query: string;
  include_similar?: boolean;
  similarity_threshold?: number;
}

/**
 * A matched product feature from the query.
 */
export interface MatchedFeature {
  feature_name: string;
  feature_description: string;
  similarity_score: number;
  source_url: string | null;
  is_core_feature: boolean;
}

/**
 * Response from a feature query.
 */
export interface FeatureQueryResponse {
  query: string;
  feature_exists: boolean;
  confidence: number;
  response_text: string;
  matched_features: MatchedFeature[];
  similar_features: MatchedFeature[];
}

// ============================================================================
// V2 COMPETITIVE ANALYSIS TYPES
// ============================================================================

/**
 * Competitor context from functional audit.
 */
export interface CompetitorContext {
  positioning: string;
  core_differentiation: string;
  target_customer: string;
}

/**
 * Feature comparison entry from functional audit.
 */
export interface FunctionalComparison {
  competitor_feature_name: string;
  functional_description: string;
  mapping_status: 'Gap' | 'Parity' | 'Advantage' | 'Differentiator';
  our_equivalent?: string | null;
  notes?: string | null;
}

/**
 * Gap deep-dive entry from functional audit.
 */
export interface GapDeepDive {
  feature_name: string;
  user_problem: string;
  evidence: string;
}

/**
 * Technical constraints from functional audit.
 */
export interface TechnicalConstraints {
  integrations?: string[];
  api_capabilities?: string;
  platform_requirements?: string;
  notes?: string;
}

/**
 * Summary of a functional report for list views.
 */
export interface FunctionalReportSummary {
  id: number;
  product_competitor_id: number;
  competitor_name: string;
  competitor_url: string | null;
  report_version: number;
  features_compared: number;
  gaps_identified: number;
  generated_at: string;
  job_status: string | null;
}

/**
 * Full functional report detail.
 */
export interface FunctionalReportDetail {
  id: number;
  product_competitor_id: number;
  competitor_name: string;
  competitor_url: string | null;
  report_version: number;
  report_content_md: string | null;
  competitor_context: CompetitorContext | null;
  functional_comparison: FunctionalComparison[];
  gaps_deep_dive: GapDeepDive[];
  technical_constraints: TechnicalConstraints | null;
  generated_at: string;
  job_status: string | null;
}

/**
 * Feature cluster entry from landscape synthesis.
 */
export interface FeatureClusterEntry {
  feature_category: string;
  prevalence: 'Table Stakes' | 'Common' | 'Emerging' | 'Frontier';
  our_status: 'Have' | 'Gap' | 'Partial';
  competitors_with_feature: string[];
  notes?: string | null;
}

/**
 * Feature opportunity from landscape synthesis.
 */
export interface FeatureOpportunity {
  feature_name: string;
  summary: string;
  user_value: string;
  market_context: string;
  priority_score: number;
  competitors_with_feature: string[];
  source_evidence: string[];
  high_impact?: boolean;
  user_sentiment?: string;
  priority_rationale?: string;
}

/**
 * High-impact gap from landscape synthesis.
 */
export interface HighImpactGap {
  rank: number;
  feature_name: string;
  market_gravity: string;
  competitors_with_feature: string[];
  user_demand_evidence: string;
}

/**
 * Landscape report detail.
 */
export interface LandscapeReportDetail {
  id: number;
  product_id: number;
  report_version: number;
  report_content_md: string | null;
  feature_cluster_matrix: FeatureClusterEntry[];
  feature_opportunities: FeatureOpportunity[];
  high_impact_gaps: HighImpactGap[];
  innovation_whitespace: string | null;
  analysis_summary: string | null;
  source_competitor_report_ids: number[];
  source_competitor_names: string[] | null;
  competitor_count: number;
  generated_at: string;
  job_status: string | null;
}

/**
 * Idea status for a gap or opportunity.
 */
export interface IdeaStatusResponse {
  idea_created: boolean;
  idea_id: number | null;
}

/**
 * Batch idea statuses response.
 */
export interface BatchIdeaStatusesResponse {
  statuses: Record<number, IdeaStatusResponse>;
  total_ideas_created: number;
}

/**
 * Response from creating ideas (gaps or opportunities).
 */
export interface CreateIdeasResponse {
  job_id: number;
  job_uuid: string;
  job_type: string;
  status: string;
  message: string;
  warning?: string;
}

/**
 * Feature opportunities export format.
 */
export interface FeatureOpportunitiesExport {
  version: string;
  generated_at: string;
  product_id: number;
  product_name: string;
  feature_ideas: FeatureOpportunity[];
  metadata: {
    total_competitors_analyzed: number;
    report_ids: number[];
  };
}

// ============================================================================
// INTERNAL FEEDBACK TYPES (Phase 2 - Internal Discovery Agent)
// ============================================================================

/**
 * Status of an internal feedback import.
 */
export type ImportStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed';

/**
 * Source type for internal feedback.
 */
export type InternalFeedbackSourceType =
  | 'file_import'
  | 'hubspot'
  | 'salesforce'
  | 'zendesk';

/**
 * Internal feedback import record.
 */
export interface InternalFeedbackImport {
  id: number;
  product_id: number;
  filename: string;
  source_type: string;
  status: string;
  error_message: string | null;
  deals_count: number;
  tickets_count: number;
  themes_extracted: boolean;
  imported_at: string;
}

/**
 * Win/loss theme extracted from deal data.
 */
export interface WinLossTheme {
  id: number;
  import_id: number;
  theme_name: string;
  outcome: 'won' | 'lost';
  competitor_name: string | null;
  deal_count: number;
  total_value: number | null;
  sample_reasons: string[];
  feature_keywords: string[];
}

/**
 * Support theme extracted from ticket data.
 */
export interface SupportTheme {
  id: number;
  import_id: number;
  theme_name: string;
  ticket_count: number;
  category: string;
  sample_subjects: string[];
  feature_keywords: string[];
  urgency_indicator: 'high' | 'medium' | 'low' | null;
}

/**
 * Combined themes response.
 */
export interface InternalFeedbackThemes {
  import_id: number;
  winloss_themes: WinLossTheme[];
  support_themes: SupportTheme[];
  analysis_summary: string | null;
}

/**
 * Import status response (for polling).
 */
export interface ImportStatusResponse {
  id: number;
  status: string;
  themes_extracted: boolean;
  winloss_theme_count: number;
  support_theme_count: number;
  error_message: string | null;
}

// ============================================================================
// ACTIVITY INSIGHT TYPES (CRM Activity Stream Analysis)
// ============================================================================

/**
 * Activity import record for CRM activity data.
 */
export interface ActivityImport {
  id: number;
  product_id: number;
  filename: string;
  source_type: 'salesforce' | 'hubspot' | 'manual' | string;
  format_type: 'json' | 'markdown';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message: string | null;
  deals_count: number;
  activities_count: number;
  support_tickets_count: number;
  analysis_summary: string | null;
  top_loss_themes: string[];
  top_win_themes: string[];
  competitor_patterns: Record<string, string[]>;
  job_uuid: string | null;
  imported_at: string;
  processed_at: string | null;
}

/**
 * Insight extracted from deal activities.
 */
export interface DealActivityInsight {
  id: number;
  import_id: number;
  product_id: number;
  deal_id: string | null;
  deal_name: string | null;
  deal_outcome: 'won' | 'lost' | 'open' | string;
  deal_value: number | null;
  competitor_mentioned: string | null;
  theme_name: string;
  category: 'feature_gap' | 'ux_friction' | 'competitive_pressure' | 'use_case_gap' | 'integration_need' | string;
  sentiment: 'positive' | 'negative' | 'neutral' | string;
  urgency_level: 'high' | 'medium' | 'low';
  sample_quotes: string[];
  activity_count: number;
  feature_keywords: string[];
}

/**
 * Insight extracted from support activities.
 */
export interface SupportActivityInsight {
  id: number;
  import_id: number;
  product_id: number;
  theme_name: string;
  category: 'feature_gap' | 'ux_friction' | 'workaround_needed' | 'integration_need' | string;
  ticket_count: number;
  urgency_level: 'high' | 'medium' | 'low';
  sample_quotes: string[];
  accounts_affected: string[];
  feature_keywords: string[];
}

/**
 * Combined activity insights response.
 */
export interface ActivityInsights {
  import_id: number;
  deal_insights: DealActivityInsight[];
  support_insights: SupportActivityInsight[];
  analysis_summary: string | null;
  top_loss_themes: string[];
  top_win_themes: string[];
  competitor_patterns: Record<string, string[]>;
}

/**
 * Activity import status response (for polling).
 */
export interface ActivityImportStatusResponse {
  id: number;
  status: string;
  deals_count: number;
  activities_count: number;
  deal_insights_count: number;
  support_insights_count: number;
  error_message: string | null;
}

// ============================================================================
// SYNTHESIS TYPES
// ============================================================================

/**
 * Sources available for synthesis.
 */
export interface SynthesisSourcesAvailable {
  competitive: boolean;
  competitive_detail: string | null;
  customer: boolean;
  customer_detail: string | null;
  internal: boolean;
  internal_detail: string | null;
  evidence: boolean;
  evidence_detail: string | null;
}

/**
 * Snapshot of sources used in a synthesis run.
 */
export interface SourceSnapshot {
  landscape_report_id: number | null;
  competitive_opportunities_count: number;
  ideas_count: number;
  ideas_total_votes: number;
  internal_import_id: number | null;
  winloss_themes_count: number;
  support_themes_count: number;
}

/**
 * Summary statistics from synthesis.
 */
export interface SummaryStats {
  three_way_matches: number;
  two_way_matches: number;
  single_source: number;
  total_opportunities: number;
}

/**
 * Synthesis run record.
 */
export interface SynthesisRun {
  id: number;
  product_id: number;
  status: string;
  error_message: string | null;
  source_snapshot: SourceSnapshot | null;
  sources_used: string[];
  summary_stats: SummaryStats | null;
  analysis_summary: string | null;
  job_uuid: string | null;
  created_at: string;
  completed_at: string | null;
  opportunity_count: number;
}

/**
 * Evidence from competitive analysis.
 */
export interface CompetitiveEvidence {
  feature_name: string;
  prevalence: string | null;
  competitors: string[];
  competitor_count: number;
  our_status: string | null;
  priority_score: number | null;
}

/**
 * Evidence from customer feedback.
 */
export interface CustomerEvidence {
  idea_id: number;
  idea_title: string;
  vote_count: number;
  status: string | null;
  submitted_at: string | null;
}

/**
 * Evidence from win/loss analysis.
 */
export interface WinLossEvidence {
  theme_id: number;
  theme_name: string;
  outcome: string;
  deal_count: number;
  total_value: number;
  competitor_correlation: string | null;
}

/**
 * Evidence from support themes.
 */
export interface SupportEvidence {
  theme_id: number;
  theme_name: string;
  ticket_count: number;
  category: string;
  urgency_indicator: string | null;
}

/**
 * Combined internal evidence.
 */
export interface InternalEvidence {
  winloss: WinLossEvidence | null;
  support: SupportEvidence | null;
}

/**
 * Synthesized opportunity.
 */
export interface EvidenceSignalItem {
  evidence_id: number;
  title: string;
  evidence_type: string;
  source_url: string | null;
  source_description: string | null;
  relevance: string;
}

export interface EvidenceSignals {
  items: EvidenceSignalItem[];
}

export interface SynthesizedOpportunity {
  id: number;
  synthesis_run_id: number;
  product_id: number;
  opportunity_name: string;
  opportunity_summary: string | null;
  priority_score: number;
  source_count: number;
  sources: string[];
  competitive_evidence: CompetitiveEvidence | null;
  customer_evidence: CustomerEvidence | null;
  internal_evidence: InternalEvidence | null;
  evidence_signals: EvidenceSignals | null;
  recommended_action: string | null;
  feature_keywords: string[];
  linked_idea_id: number | null;
  created_at: string;
}

/**
 * Synthesis status response.
 */
export interface SynthesisStatusResponse {
  product_id: number;
  sources_available: SynthesisSourcesAvailable;
  has_previous_run: boolean;
  previous_run: SynthesisRun | null;
}

/**
 * Full synthesis results response.
 */
export interface SynthesisResultsResponse {
  run: SynthesisRun;
  opportunities: SynthesizedOpportunity[];
}

// --- Idea Lifecycle & Funnel ---

export interface IdeaLifecycleStatus {
  id: number;
  name: string;
  slug: string;
  color: string;
  position: number;
  is_default: boolean;
  is_active: boolean;
  idea_count: number;
}

export interface IdeaFunnelData {
  product_id: number;
  total_submitted: number;
  status_counts: Record<string, number>;
  lifecycle_counts: Record<string, number>;
  auto_triaged_count: number;
  manual_triaged_count: number;
}

// ============================================================================
// Evidence / Factbase
// ============================================================================

export type EvidenceType =
  | 'competitive_intel'
  | 'customer_interview'
  | 'market_signal'
  | 'internal_note'
  | 'research'
  | 'pricing_change'
  | 'partnership'
  | 'product_launch'
  | 'analyst_report';

export interface EvidenceRecord {
  id: number;
  evidence_type: EvidenceType;
  title: string;
  source_url: string | null;
  source_description: string | null;
  competitor_id: number | null;
  competitor_name?: string | null;
  tags: string[] | null;
  jtbd_statement: string | null;
  created_at: string;
}

export interface EvidenceDetail extends EvidenceRecord {
  product_id: number;
  content: string;
  created_by: string;
  updated_at: string | null;
}

export interface EvidenceListResponse {
  product_id: number;
  count: number;
  evidence: EvidenceRecord[];
}

export interface CreateEvidenceRequest {
  evidence_type: EvidenceType;
  title: string;
  content: string;
  source_url?: string;
  source_description?: string;
  competitor_id?: number;
  competitor_name?: string;
  competitor_url?: string;
  tags?: string[];
}

export interface CompetitorSuggestion {
  suggested_name: string | null;
  matched_competitor_id: number | null;
  matched_competitor_name: string | null;
  is_new: boolean;
}
