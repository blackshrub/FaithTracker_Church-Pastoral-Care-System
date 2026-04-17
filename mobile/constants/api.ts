/**
 * FaithTracker API Endpoints
 *
 * All endpoints are relative to EXPO_PUBLIC_API_URL
 */

export const API_ENDPOINTS = {
  // Auth
  AUTH: {
    LOGIN: '/auth/login',
    LOGOUT: '/auth/logout',
    REFRESH: '/auth/refresh',
    ME: '/auth/me',
    REGISTER: '/auth/register',
  },

  // Users
  USERS: {
    LIST: '/users',
    DETAIL: (id: string) => `/users/${id}`,
    PHOTO: (id: string) => `/users/${id}/photo`,
  },

  // Members
  MEMBERS: {
    LIST: '/members',
    DETAIL: (id: string) => `/members/${id}`,
    CREATE: '/members',
    UPDATE: (id: string) => `/members/${id}`,
    DELETE: (id: string) => `/members/${id}`,
    PHOTO: (id: string) => `/members/${id}/photo`,
    AT_RISK: '/members/at-risk',
  },

  // Care Events
  CARE_EVENTS: {
    LIST: '/care-events',
    DETAIL: (id: string) => `/care-events/${id}`,
    CREATE: '/care-events',
    UPDATE: (id: string) => `/care-events/${id}`,
    DELETE: (id: string) => `/care-events/${id}`,
    COMPLETE: (id: string) => `/care-events/${id}/complete`,
    IGNORE: (id: string) => `/care-events/${id}/ignore`,
    VISITATION_LOG: (id: string) => `/care-events/${id}/visitation-log`,
    ADDITIONAL_VISIT: (parentId: string) => `/care-events/${parentId}/additional-visit`,
  },

  // Grief Support
  GRIEF_SUPPORT: {
    LIST: '/grief-support',
    MEMBER: (memberId: string) => `/grief-support/member/${memberId}`,
    COMPLETE: (stageId: string) => `/grief-support/${stageId}/complete`,
    IGNORE: (stageId: string) => `/grief-support/${stageId}/ignore`,
    UNDO: (stageId: string) => `/grief-support/${stageId}/undo`,
  },

  // Accident Followup
  ACCIDENT_FOLLOWUP: {
    LIST: '/accident-followup',
    MEMBER: (memberId: string) => `/accident-followup/member/${memberId}`,
    COMPLETE: (stageId: string) => `/accident-followup/${stageId}/complete`,
    IGNORE: (stageId: string) => `/accident-followup/${stageId}/ignore`,
    UNDO: (stageId: string) => `/accident-followup/${stageId}/undo`,
  },

  // Financial Aid
  FINANCIAL_AID: {
    SCHEDULES: '/financial-aid-schedules',
    MEMBER: (memberId: string) => `/financial-aid-schedules/member/${memberId}`,
    DUE_TODAY: '/financial-aid-schedules/due-today',
    MARK_DISTRIBUTED: (id: string) => `/financial-aid-schedules/${id}/mark-distributed`,
    IGNORE: (id: string) => `/financial-aid-schedules/${id}/ignore`,
    STOP: (id: string) => `/financial-aid-schedules/${id}/stop`,
    SUMMARY: '/financial-aid/summary',
    RECIPIENTS: '/financial-aid/recipients',
  },

  // Dashboard
  DASHBOARD: {
    REMINDERS: '/dashboard/reminders',
    STATS: '/dashboard/stats',
    UPCOMING: '/dashboard/upcoming',
    GRIEF_ACTIVE: '/dashboard/grief-active',
    RECENT_ACTIVITY: '/dashboard/recent-activity',
  },

  // Campuses
  CAMPUSES: {
    LIST: '/campuses',
    DETAIL: (id: string) => `/campuses/${id}`,
  },

  // Config
  CONFIG: {
    ALL: '/config/all',
    AID_TYPES: '/config/aid-types',
    EVENT_TYPES: '/config/event-types',
  },

  // Activity Stream
  ACTIVITY: {
    STREAM: '/stream/activity',
    LOGS: '/activity-logs',
  },

  // Analytics
  ANALYTICS: {
    DASHBOARD: '/analytics/dashboard',
    ENGAGEMENT_TRENDS: '/analytics/engagement-trends',
    DEMOGRAPHIC_TRENDS: '/analytics/demographic-trends',
  },

  // Reports
  REPORTS: {
    MONTHLY: '/reports/monthly',
    MONTHLY_PDF: '/reports/monthly/pdf',
    STAFF_PERFORMANCE: '/reports/staff-performance',
    YEARLY_SUMMARY: '/reports/yearly-summary',
  },
} as const;

// Event types
export const EVENT_TYPES = [
  'birthday',
  'grief_loss',
  'accident_illness',
  'financial_aid',
  'regular_contact',
  'childbirth',
  'new_house',
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

// Engagement statuses
export const ENGAGEMENT_STATUSES = ['active', 'at_risk', 'disconnected'] as const;
export type EngagementStatus = (typeof ENGAGEMENT_STATUSES)[number];

// User roles
export const USER_ROLES = ['full_admin', 'campus_admin', 'pastor'] as const;
export type UserRole = (typeof USER_ROLES)[number];

// Aid types
export const AID_TYPES = [
  'education',
  'medical',
  'emergency',
  'housing',
  'food',
  'funeral_costs',
  'other',
] as const;
export type AidType = (typeof AID_TYPES)[number];

// Grief relationships
export const GRIEF_RELATIONSHIPS = ['spouse', 'child', 'parent', 'sibling', 'other'] as const;
export type GriefRelationship = (typeof GRIEF_RELATIONSHIPS)[number];
