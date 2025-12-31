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
  MANUAL = 'manual',
  AI_GENERATED = 'ai_generated',
}

export enum IdeaStatus {
  SUBMITTED = 'submitted',
  UNDER_REVIEW = 'under_review',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  IMPLEMENTED = 'implemented',
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
  downvotes: number;
  score: number;
  total_votes: number;
}

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
  // Triage status fields
  triage_status: TriageStatus | null;
  is_active: boolean | null;
  auto_responded: boolean | null;
  duplicate_of_idea_id: number | null;
  duplicate_of_title: string | null;
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
// TRIAGE STATUS TYPES (Plan Phase 2)
// ============================================================================

export enum TriageStatus {
  PENDING = 'pending',
  AUTO_APPROVED = 'auto_approved',
  NEEDS_REVIEW = 'needs_review',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  DUPLICATE = 'duplicate',
  FEATURE_EXISTS = 'feature_exists',
  NOT_APPROPRIATE = 'not_appropriate',
}

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

export interface IdeaDetail {
  id: number;
  title: string;
  what_description: string;
  why_description: string;
  use_case_description: string;
  source_type: string;
  category: string | null;
  status: string;
  triage_status: TriageStatus;
  triage_confidence: number | null;
  triage_recommendation: string | null;
  triage_reasoning: string | null;
  duplicate_of_idea_id: number | null;
  duplicate_of_title: string | null;
  similarity_score: number | null;
  auto_response_text: string | null;
  is_active: boolean;
  auto_responded: boolean;
  published_for_voting: boolean;
  product_id: number;
  product_name: string | null;
  submitter_id: number | null;
  submitter_username: string | null;
  reviewed_by_user_id: number | null;
  reviewer_username: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string;
  updated_at: string;
  comments: IdeaComment[];
  status_history: StatusHistoryEntry[];
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
  status: IdeaResponseStatus;
  triage_status: TriageStatus;
  is_active: boolean;
  published_for_voting: boolean;
  duplicate_of_idea_id: number | null;
  responded_by: string;
  responded_at: string;
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

export interface SourceSummary {
  vote_count: number;
  downvote_count: number;
  voters: IdeaVoter[];
  competitors_with_feature: string[];
  competitive_urgency: string | null;
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
  ideas_auto_responded: number;
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
