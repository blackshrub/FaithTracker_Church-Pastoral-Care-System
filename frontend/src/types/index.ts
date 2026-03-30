/**
 * Core domain types for FaithTracker frontend.
 * These match the backend msgspec Struct definitions.
 *
 * Usage from .js/.jsx files:
 *   /** @type {import('@/types').Member} *\/
 *   const member = data;
 */

// ==================== ENUMS ====================

export type EngagementStatus = 'active' | 'at_risk' | 'disconnected';

export type EventType =
  | 'birthday'
  | 'childbirth'
  | 'grief_loss'
  | 'new_house'
  | 'accident_illness'
  | 'financial_aid'
  | 'regular_contact';

export type UserRole = 'full_admin' | 'campus_admin' | 'pastor';

export type AidType =
  | 'education'
  | 'medical'
  | 'housing'
  | 'family'
  | 'food'
  | 'transportation'
  | 'emergency';

export type GriefStageKey =
  | '1_week'
  | '2_weeks'
  | '1_month'
  | '3_months'
  | '6_months'
  | '1_year';

export type AccidentStageKey =
  | 'first_followup'
  | 'second_followup'
  | 'final_followup';

// ==================== CORE MODELS ====================

export interface Member {
  id: string;
  campus_id: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  birth_date?: string | null;
  address?: string | null;
  category?: string | null;
  gender?: string | null;
  blood_type?: string | null;
  marital_status?: string | null;
  membership_status?: string | null;
  age?: number | null;
  notes?: string | null;
  engagement_status: EngagementStatus;
  days_since_last_contact: number;
  last_contact_date?: string | null;
  is_archived: boolean;
  photo_url?: string | null;
  external_member_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CareEvent {
  id: string;
  campus_id: string;
  member_id: string;
  event_type: EventType;
  event_date: string;
  title: string;
  description?: string | null;
  completed: boolean;
  completed_at?: string | null;
  completed_by_user_id?: string | null;
  completed_by_user_name?: string | null;
  ignored: boolean;
  ignored_at?: string | null;
  ignored_by?: string | null;
  ignored_by_name?: string | null;
  aid_type?: string | null;
  aid_amount?: number | null;
  aid_notes?: string | null;
  hospital_name?: string | null;
  grief_relationship?: string | null;
  grief_stage_id?: string | null;
  accident_stage_id?: string | null;
  care_event_id?: string | null;
  followup_type?: string | null;
  created_by_user_id?: string | null;
  created_by_user_name?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  campus_id?: string | null;
  phone?: string | null;
  photo_url?: string | null;
  is_active: boolean;
}

export interface Campus {
  id: string;
  campus_name: string;
  location?: string | null;
  timezone: string;
  is_active: boolean;
}

// ==================== FOLLOW-UP MODELS ====================

export interface GriefStage {
  id: string;
  campus_id: string;
  member_id: string;
  care_event_id: string;
  stage: GriefStageKey;
  stage_name: string;
  scheduled_date: string;
  completed: boolean;
  completed_at?: string | null;
  completed_by_user_id?: string | null;
  completed_by_user_name?: string | null;
  ignored?: boolean;
  ignored_at?: string | null;
  ignored_by?: string | null;
  ignored_by_name?: string | null;
  notes?: string | null;
  reminder_sent?: boolean;
}

export interface AccidentFollowup {
  id: string;
  campus_id: string;
  member_id: string;
  care_event_id: string;
  stage: AccidentStageKey;
  scheduled_date: string;
  completed: boolean;
  completed_at?: string | null;
  completed_by_user_id?: string | null;
  completed_by_user_name?: string | null;
  ignored?: boolean;
  ignored_at?: string | null;
  ignored_by?: string | null;
  ignored_by_name?: string | null;
}

// ==================== FINANCIAL AID ====================

export interface FinancialAidSchedule {
  id: string;
  campus_id: string;
  member_id: string;
  title: string;
  aid_type: string;
  aid_amount: number;
  frequency: 'weekly' | 'biweekly' | 'monthly' | 'quarterly' | 'one_time';
  start_date: string;
  end_date?: string | null;
  day_of_week?: number | null;
  next_occurrence?: string | null;
  is_active: boolean;
  ignored?: boolean;
  ignored_occurrences?: string[];
  distribution_history?: DistributionRecord[];
  created_at: string;
}

export interface DistributionRecord {
  date: string;
  distributed_by_user_id: string;
  distributed_by_user_name: string;
  amount: number;
  notes?: string;
}

// ==================== ACTIVITY & NOTES ====================

export interface ActivityLog {
  id: string;
  campus_id: string;
  user_id: string;
  user_name: string;
  user_photo_url?: string | null;
  action_type: string;
  member_id?: string | null;
  member_name?: string | null;
  care_event_id?: string | null;
  event_type?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface PastoralNote {
  id: string;
  member_id: string;
  campus_id: string;
  title: string;
  content: string;
  category?: string | null;
  is_private: boolean;
  follow_up_date?: string | null;
  follow_up_completed?: boolean;
  follow_up_notes?: string | null;
  author_id: string;
  author_name: string;
  created_at: string;
  updated_at?: string;
}

// ==================== DASHBOARD ====================

export interface DashboardTask {
  type: 'grief_support' | 'accident_followup' | 'financial_aid';
  member_id: string;
  member_name: string;
  member_phone?: string | null;
  member_photo_url?: string | null;
  details: string;
  date: string;
  days_overdue?: number;
  data: GriefStage | AccidentFollowup | FinancialAidSchedule;
}

export interface DashboardBirthday {
  member_id: string;
  member_name: string;
  member_phone?: string | null;
  member_photo_url?: string | null;
  date: string;
  event_id: string;
  days_overdue?: number;
}

export interface DashboardData {
  birthdays_today: DashboardBirthday[];
  overdue_birthdays: DashboardBirthday[];
  upcoming_birthdays: DashboardBirthday[];
  today_tasks: DashboardTask[];
  grief_today: GriefStage[];
  accident_followup: AccidentFollowup[];
  at_risk_members: Member[];
  disconnected_members: Member[];
  financial_aid_due: FinancialAidSchedule[];
  ai_suggestions: string[];
  upcoming_tasks: DashboardTask[];
  total_tasks: number;
  total_members: number;
  cache_source?: string;
}

// ==================== API RESPONSES ====================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}
