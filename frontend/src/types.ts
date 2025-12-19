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
