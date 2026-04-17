/**
 * FaithTracker Mobile Type Definitions
 */

import type { EventType, EngagementStatus, UserRole, AidType, GriefRelationship } from '@/constants/api';

// Re-export API types
export type { EventType, EngagementStatus, UserRole, AidType, GriefRelationship } from '@/constants/api';

// ============================================================================
// USER & AUTH
// ============================================================================

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  campus_id: string;
  campus_name: string;
  phone?: string;
  photo_url?: string;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  campus_id?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
  /** Long-lived opaque refresh token. Present on fresh login; mobile persists
   *  it in SecureStore and exchanges it via POST /auth/refresh when the
   *  access token expires. */
  refresh_token?: string | null;
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
  refresh_token?: string | null;
}

// ============================================================================
// MEMBER
// ============================================================================

export interface Member {
  id: string;
  name: string;
  phone?: string;
  campus_id: string;
  photo_url?: string;
  last_contact_date?: string;
  engagement_status: EngagementStatus;
  days_since_last_contact?: number;
  is_archived: boolean;
  archived_at?: string;
  archived_reason?: string;
  external_member_id?: string;
  notes?: string;
  birth_date?: string;
  address?: string;
  category?: string;
  gender?: 'M' | 'F';
  blood_type?: string;
  marital_status?: string;
  membership_status?: string;
  age?: number;
  created_at: string;
  updated_at: string;
}

export interface MemberListItem {
  id: string;
  name: string;
  phone?: string;
  campus_id: string;
  photo_url?: string;
  last_contact_date?: string;
  engagement_status: EngagementStatus;
  days_since_last_contact?: number;
  is_archived: boolean;
  external_member_id?: string;
  age?: number;
  gender?: 'M' | 'F';
  category?: string;
}

export interface CreateMemberRequest {
  name: string;
  phone?: string;
  campus_id: string;
  external_member_id?: string;
  notes?: string;
  birth_date?: string;
  address?: string;
  category?: string;
  gender?: 'M' | 'F';
  blood_type?: string;
  marital_status?: string;
  membership_status?: string;
  age?: number;
}

// ============================================================================
// CARE EVENT
// ============================================================================

export interface CareEvent {
  id: string;
  member_id: string;
  member_name: string;
  campus_id: string;
  event_type: EventType;
  event_date: string;
  title: string;
  description?: string;
  completed: boolean;
  completed_at?: string;
  completed_by_user_id?: string;
  completed_by_user_name?: string;
  ignored: boolean;
  ignored_at?: string;
  ignored_by?: string;
  ignored_by_name?: string;
  created_by_user_id: string;
  created_by_user_name: string;
  created_at: string;
  updated_at: string;
  // Type-specific fields
  grief_relationship?: GriefRelationship;
  hospital_name?: string;
  discharge_date?: string;
  aid_type?: AidType;
  aid_amount?: number;
  aid_notes?: string;
  visitation_logs?: VisitationLog[];
}

export interface CreateCareEventRequest {
  member_id: string;
  campus_id: string;
  event_type: EventType;
  event_date: string;
  title: string;
  description?: string;
  // Type-specific fields
  grief_relationship?: GriefRelationship;
  hospital_name?: string;
  initial_visitation?: {
    visitor_name: string;
    visit_date: string;
    notes?: string;
    prayer_offered?: boolean;
  };
  aid_type?: AidType;
  aid_amount?: number;
  aid_notes?: string;
}

export interface VisitationLog {
  visitor_name: string;
  visit_date: string;
  notes?: string;
  prayer_offered?: boolean;
}

// ============================================================================
// GRIEF SUPPORT
// ============================================================================

export interface GriefStage {
  id: string;
  care_event_id: string;
  member_id: string;
  member_name?: string;
  member_phone?: string;
  member_photo_url?: string;
  campus_id: string;
  stage: string;
  stage_type?: string;
  scheduled_date: string;
  completed: boolean;
  completed_at?: string;
  completed_by_user_name?: string;
  ignored: boolean;
  ignored_at?: string;
  ignored_by?: string;
  notes?: string;
  reminder_sent: boolean;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// ACCIDENT FOLLOWUP
// ============================================================================

export type AccidentFollowupStage = 'first_followup' | 'second_followup' | 'final_followup';

export interface AccidentFollowup {
  id: string;
  care_event_id: string;
  member_id: string;
  member_name?: string;
  member_phone?: string;
  member_photo_url?: string;
  campus_id: string;
  stage: AccidentFollowupStage;
  stage_type?: AccidentFollowupStage;
  scheduled_date: string;
  hospital_name?: string;
  completed: boolean;
  completed_at?: string;
  completed_by_user_name?: string;
  ignored: boolean;
  ignored_at?: string;
  ignored_by?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// FINANCIAL AID
// ============================================================================

export interface FinancialAidSchedule {
  id: string;
  member_id: string;
  member_name?: string;
  member_phone?: string;
  member_photo_url?: string;
  campus_id: string;
  title: string;
  aid_type: AidType;
  aid_amount: number;
  amount?: number;
  frequency: 'one_time' | 'weekly' | 'monthly' | 'annually';
  start_date: string;
  scheduled_date?: string;
  payment_date?: string;
  end_date?: string;
  day_of_week?: string;
  day_of_month?: number;
  month_of_year?: number;
  is_active: boolean;
  ignored: boolean;
  ignored_occurrences: string[];
  next_occurrence?: string;
  occurrences_completed: number;
  distributed?: boolean;
  distributed_at?: string;
  distributed_by_user_name?: string;
  created_by: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// DASHBOARD
// ============================================================================

export interface DashboardReminders {
  birthdays_today: DashboardTask[];
  overdue_birthdays: DashboardTask[];  // Past birthdays not yet completed
  upcoming_birthdays: DashboardTask[];
  upcoming_tasks: DashboardTask[];  // All upcoming tasks (birthdays, accidents, financial aid, etc.)
  today_tasks: DashboardTask[];  // All tasks due today (birthdays, grief, accidents, financial aid)
  grief_today: DashboardTask[];
  accident_followup: DashboardTask[];
  at_risk_members: DashboardTask[];
  disconnected_members: DashboardTask[];
  financial_aid_due: DashboardTask[];
  ai_suggestions: any[];
  total_tasks: number;
  total_members: number;
  cache_version?: string;
}

export interface DashboardTask {
  type: string;
  member_id: string;
  member_name: string;
  member_phone?: string;
  member_photo_url?: string;
  member_age?: number;
  // Event-specific fields
  event_id?: string;
  stage_id?: string;
  stage?: string;
  scheduled_date?: string;
  aid_amount?: number;
  aid_type?: AidType;
  title?: string;
  days_since_last_contact?: number;
  // Additional fields from backend
  event_type?: EventType;           // Backend returns this for care events
  date?: string;                    // Alternative date field
  next_distribution_date?: string;  // Financial aid next distribution
  schedule_id?: string;             // Financial aid schedule identifier
  phone?: string;                   // Alternative phone field (at-risk/disconnected)
  age?: number;                     // Alternative age field (at-risk/disconnected)
  id?: string;                      // At-risk/disconnected members use id
  name?: string;                    // At-risk/disconnected format uses name
  photo_url?: string;               // At-risk/disconnected format uses photo_url
  days_overdue?: number;            // Overdue tasks
  hospital_name?: string;           // Accident/illness events
  grief_relationship?: GriefRelationship; // Grief events
}

export interface DashboardStats {
  total_members: number;
  active_grief_support: number;
  members_at_risk: number;
  month_financial_aid: number;
}

// ============================================================================
// CAMPUS
// ============================================================================

export interface Campus {
  id: string;
  campus_name: string;
  location?: string;
  timezone: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// PAGINATION
// ============================================================================

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}

export interface MemberFilters {
  search?: string;
  engagement_status?: EngagementStatus;
  show_archived?: boolean;
  page?: number;
  limit?: number;
}

export interface CareEventFilters {
  member_id?: string;
  event_type?: EventType;
  completed?: boolean;
  page?: number;
  limit?: number;
}

// ============================================================================
// ACTIVITY STREAM
// ============================================================================

export type ActivityActionType =
  | 'complete_task'
  | 'ignore_task'
  | 'unignore_task'
  | 'send_reminder'
  | 'stop_schedule'
  | 'clear_ignored'
  | 'create_member'
  | 'update_member'
  | 'delete_member'
  | 'create_care_event'
  | 'update_care_event'
  | 'delete_care_event';

export interface ActivityEvent {
  id: string;
  campus_id: string;
  user_id: string;
  user_name: string;
  user_photo_url?: string;
  action_type: ActivityActionType;
  member_id?: string;
  member_name?: string;
  care_event_id?: string;
  event_type?: EventType;
  notes?: string;
  timestamp: string;
}

// ============================================================================
// ANALYTICS
// ============================================================================

export interface AnalyticsDashboard {
  member_stats: {
    total: number;
    active: number;
    at_risk: number;
    disconnected: number;
    new_this_month: number;
  };
  demographics: {
    age_distribution: { range: string; count: number }[];
    gender_distribution: { gender: string; count: number }[];
    category_distribution: { category: string; count: number }[];
    membership_distribution: { status: string; count: number }[];
  };
  events_by_type: { type: EventType; count: number; completed: number }[];
  events_by_month: { month: string; count: number }[];
  financial: {
    total_distributed: number;
    total_pending: number;
    by_type: { type: AidType; amount: number; count: number }[];
  };
  engagement_trends: {
    date: string;
    active: number;
    at_risk: number;
    disconnected: number;
  }[];
}

// ============================================================================
// REPORTS
// ============================================================================

export interface MonthlyReport {
  report_period: {
    year: number;
    month: number;
    month_name: string;
  };
  executive_summary: {
    total_members: number;
    active_members: number;
    tasks_completed: number;
    completion_rate: number;
  };
  kpis: {
    care_completion_rate: number;
    engagement_rate: number;
    reach_rate: number;
    birthday_completion_rate: number;
  };
  ministry_highlights: {
    new_members: number;
    grief_support_active: number;
    financial_aid_distributed: number;
    hospital_visits: number | { patients_visited?: number };
    grief_support?: { families_supported?: number };
  };
  care_breakdown: {
    type: EventType;
    total: number;
    completed: number;
    rate: number;
  }[];
  insights: string[];
  recommendations: string[];
}

export interface StaffPerformanceReport {
  period: {
    year: number;
    month: number;
  };
  team_overview: {
    total_staff: number;
    total_tasks_completed: number;
    average_per_staff: number;
  };
  staff_metrics: {
    user_id: string;
    user_name: string;
    user_photo_url?: string;
    tasks_completed: number;
    members_contacted: number;
    active_days: number;
    rank: number;
  }[];
}
