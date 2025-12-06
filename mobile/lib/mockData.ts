/**
 * FaithTracker Mock Data
 *
 * Mock data for development and testing without backend
 * Set MOCK_MODE_ENABLED to true to use mock data
 */

import type {
  User,
  Member,
  MemberListItem,
  CareEvent,
  DashboardReminders,
  DashboardTask,
  GriefStage,
  FinancialAidSchedule,
} from '@/types';

// ============================================================================
// CONFIGURATION
// ============================================================================

/**
 * Enable/disable mock mode
 * When true, app uses mock data instead of real API
 */
export const MOCK_MODE_ENABLED = false;

// ============================================================================
// HELPERS
// ============================================================================

/**
 * Simulate network delay for realistic UX testing
 */
export function simulateApiDelay(minMs: number = 300, maxMs: number = 800): Promise<void> {
  const delay = Math.random() * (maxMs - minMs) + minMs;
  return new Promise((resolve) => setTimeout(resolve, delay));
}

/**
 * Generate a random ID
 */
function generateId(): string {
  return Math.random().toString(36).substring(2, 15);
}

/**
 * Get date N days from now
 */
function daysFromNow(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().split('T')[0];
}

/**
 * Get date N days ago
 */
function daysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().split('T')[0];
}

// ============================================================================
// MOCK USER
// ============================================================================

export const mockUser: User = {
  id: 'user_mock_001',
  email: 'pastor.budi@gkbj.org',
  name: 'Pastor Budi Santoso',
  role: 'campus_admin',
  campus_id: 'campus_mock_001',
  campus_name: 'GKBJ Kelapa Gading',
  phone: '+6281234567890',
  photo_url: undefined,
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
};

// ============================================================================
// MOCK MEMBERS
// ============================================================================

export const mockMembers: Member[] = [
  {
    id: 'member_001',
    name: 'Siti Rahayu',
    phone: '+6281234567891',
    campus_id: 'campus_mock_001',
    photo_url: undefined,
    last_contact_date: daysAgo(5),
    engagement_status: 'active',
    days_since_last_contact: 5,
    is_archived: false,
    notes: 'Active in youth ministry',
    birth_date: '1990-03-15',
    address: 'Jl. Kelapa Gading Blok A1 No. 10',
    category: 'Youth',
    gender: 'F',
    age: 34,
    created_at: '2024-01-15T00:00:00Z',
    updated_at: '2024-06-01T00:00:00Z',
  },
  {
    id: 'member_002',
    name: 'Agus Wijaya',
    phone: '+6281234567892',
    campus_id: 'campus_mock_001',
    photo_url: undefined,
    last_contact_date: daysAgo(45),
    engagement_status: 'at_risk',
    days_since_last_contact: 45,
    is_archived: false,
    notes: 'Recently lost job, needs support',
    birth_date: '1985-07-22',
    address: 'Jl. Sunter Agung No. 25',
    category: 'Adult',
    gender: 'M',
    age: 39,
    created_at: '2024-02-10T00:00:00Z',
    updated_at: '2024-05-15T00:00:00Z',
  },
  {
    id: 'member_003',
    name: 'Maria Tan',
    phone: '+6281234567893',
    campus_id: 'campus_mock_001',
    photo_url: undefined,
    last_contact_date: daysAgo(2),
    engagement_status: 'active',
    days_since_last_contact: 2,
    is_archived: false,
    notes: 'Women ministry leader',
    birth_date: '1978-11-08',
    address: 'Jl. Boulevard Raya No. 45',
    category: 'Senior',
    gender: 'F',
    age: 46,
    created_at: '2023-06-01T00:00:00Z',
    updated_at: '2024-06-10T00:00:00Z',
  },
  {
    id: 'member_004',
    name: 'Hendri Susanto',
    phone: '+6281234567894',
    campus_id: 'campus_mock_001',
    photo_url: undefined,
    last_contact_date: daysAgo(120),
    engagement_status: 'disconnected',
    days_since_last_contact: 120,
    is_archived: false,
    notes: 'Moved to new area, hard to reach',
    birth_date: '1995-04-30',
    address: 'Jl. Pegangsaan Dua No. 88',
    category: 'Youth',
    gender: 'M',
    age: 29,
    created_at: '2023-09-15T00:00:00Z',
    updated_at: '2024-02-01T00:00:00Z',
  },
  {
    id: 'member_005',
    name: 'Linda Permata',
    phone: '+6281234567895',
    campus_id: 'campus_mock_001',
    photo_url: undefined,
    last_contact_date: daysAgo(10),
    engagement_status: 'active',
    days_since_last_contact: 10,
    is_archived: false,
    notes: 'New member, very enthusiastic',
    birth_date: '2000-12-25',
    address: 'Jl. Gading Serpong No. 12',
    category: 'Youth',
    gender: 'F',
    age: 24,
    created_at: '2024-05-01T00:00:00Z',
    updated_at: '2024-06-08T00:00:00Z',
  },
  {
    id: 'member_006',
    name: 'Robert Halim',
    phone: '+6281234567896',
    campus_id: 'campus_mock_001',
    photo_url: undefined,
    last_contact_date: daysAgo(75),
    engagement_status: 'at_risk',
    days_since_last_contact: 75,
    is_archived: false,
    notes: 'Business owner, often traveling',
    birth_date: '1970-08-18',
    address: 'Jl. Pantai Indah Kapuk No. 99',
    category: 'Senior',
    gender: 'M',
    age: 54,
    created_at: '2022-01-01T00:00:00Z',
    updated_at: '2024-04-01T00:00:00Z',
  },
  {
    id: 'member_007',
    name: 'Dewi Anggraini',
    phone: '+6281234567897',
    campus_id: 'campus_mock_001',
    photo_url: undefined,
    last_contact_date: daysAgo(1),
    engagement_status: 'active',
    days_since_last_contact: 1,
    is_archived: false,
    notes: 'Choir member',
    birth_date: '1988-05-20',
    address: 'Jl. Pluit Karang No. 33',
    category: 'Adult',
    gender: 'F',
    age: 36,
    created_at: '2023-03-15T00:00:00Z',
    updated_at: '2024-06-11T00:00:00Z',
  },
  {
    id: 'member_008',
    name: 'Bambang Setiawan',
    phone: '+6281234567898',
    campus_id: 'campus_mock_001',
    photo_url: undefined,
    last_contact_date: daysAgo(30),
    engagement_status: 'active',
    days_since_last_contact: 30,
    is_archived: false,
    notes: 'Usher team coordinator',
    birth_date: '1982-09-12',
    address: 'Jl. Muara Karang No. 55',
    category: 'Adult',
    gender: 'M',
    age: 42,
    created_at: '2021-06-01T00:00:00Z',
    updated_at: '2024-05-20T00:00:00Z',
  },
];

// ============================================================================
// MOCK MEMBER LIST ITEMS (Lightweight version for list views)
// ============================================================================

export const mockMemberListItems: MemberListItem[] = mockMembers.map((m) => ({
  id: m.id,
  name: m.name,
  phone: m.phone,
  campus_id: m.campus_id,
  photo_url: m.photo_url,
  last_contact_date: m.last_contact_date,
  engagement_status: m.engagement_status,
  days_since_last_contact: m.days_since_last_contact,
  is_archived: m.is_archived,
  age: m.age,
  gender: m.gender,
  category: m.category,
}));

// ============================================================================
// MOCK CARE EVENTS
// ============================================================================

export const mockCareEvents: CareEvent[] = [
  {
    id: 'event_001',
    member_id: 'member_001',
    member_name: 'Siti Rahayu',
    campus_id: 'campus_mock_001',
    event_type: 'birthday',
    event_date: daysFromNow(0), // Today!
    title: 'Birthday - Siti Rahayu turns 34',
    description: 'Send birthday wishes and blessing',
    completed: false,
    ignored: false,
    created_by_user_id: mockUser.id,
    created_by_user_name: mockUser.name,
    created_at: daysAgo(30),
    updated_at: daysAgo(30),
  },
  {
    id: 'event_002',
    member_id: 'member_002',
    member_name: 'Agus Wijaya',
    campus_id: 'campus_mock_001',
    event_type: 'grief_loss',
    event_date: daysAgo(14),
    title: 'Loss of Father',
    description: 'Father passed away on Dec 1st. Needs ongoing grief support.',
    completed: false,
    ignored: false,
    created_by_user_id: mockUser.id,
    created_by_user_name: mockUser.name,
    created_at: daysAgo(14),
    updated_at: daysAgo(14),
    grief_relationship: 'parent',
  },
  {
    id: 'event_003',
    member_id: 'member_003',
    member_name: 'Maria Tan',
    campus_id: 'campus_mock_001',
    event_type: 'financial_aid',
    event_date: daysAgo(7),
    title: 'Education Support for Children',
    description: 'Monthly tuition assistance for 2 children',
    completed: false,
    ignored: false,
    created_by_user_id: mockUser.id,
    created_by_user_name: mockUser.name,
    created_at: daysAgo(60),
    updated_at: daysAgo(7),
    aid_type: 'education',
    aid_amount: 2500000,
    aid_notes: 'Monthly recurring until December 2024',
  },
  {
    id: 'event_004',
    member_id: 'member_005',
    member_name: 'Linda Permata',
    campus_id: 'campus_mock_001',
    event_type: 'accident_illness',
    event_date: daysAgo(3),
    title: 'Hospitalized - Appendix Surgery',
    description: 'Emergency appendectomy at RS Mitra Keluarga',
    completed: false,
    ignored: false,
    created_by_user_id: mockUser.id,
    created_by_user_name: mockUser.name,
    created_at: daysAgo(3),
    updated_at: daysAgo(3),
    hospital_name: 'RS Mitra Keluarga Kelapa Gading',
  },
  {
    id: 'event_005',
    member_id: 'member_007',
    member_name: 'Dewi Anggraini',
    campus_id: 'campus_mock_001',
    event_type: 'childbirth',
    event_date: daysAgo(5),
    title: 'New Baby - First Child',
    description: 'Baby boy born on Dec 7th. Mother and baby healthy.',
    completed: false,
    ignored: false,
    created_by_user_id: mockUser.id,
    created_by_user_name: mockUser.name,
    created_at: daysAgo(5),
    updated_at: daysAgo(5),
  },
  {
    id: 'event_006',
    member_id: 'member_008',
    member_name: 'Bambang Setiawan',
    campus_id: 'campus_mock_001',
    event_type: 'regular_contact',
    event_date: daysAgo(30),
    title: 'Monthly Check-in',
    description: 'Regular pastoral care visit',
    completed: true,
    completed_at: daysAgo(28),
    completed_by_user_id: mockUser.id,
    completed_by_user_name: mockUser.name,
    ignored: false,
    created_by_user_id: mockUser.id,
    created_by_user_name: mockUser.name,
    created_at: daysAgo(35),
    updated_at: daysAgo(28),
  },
  {
    id: 'event_007',
    member_id: 'member_006',
    member_name: 'Robert Halim',
    campus_id: 'campus_mock_001',
    event_type: 'new_house',
    event_date: daysFromNow(7),
    title: 'House Blessing',
    description: 'New house in PIK 2, scheduled for blessing next week',
    completed: false,
    ignored: false,
    created_by_user_id: mockUser.id,
    created_by_user_name: mockUser.name,
    created_at: daysAgo(10),
    updated_at: daysAgo(10),
  },
];

// ============================================================================
// MOCK GRIEF STAGES
// ============================================================================

export const mockGriefStages: GriefStage[] = [
  {
    id: 'grief_stage_001',
    care_event_id: 'event_002',
    member_id: 'member_002',
    member_name: 'Agus Wijaya',
    member_phone: '+6281234567892',
    campus_id: 'campus_mock_001',
    stage: 'Day 3 - Initial Support',
    scheduled_date: daysAgo(11),
    completed: true,
    completed_at: daysAgo(10),
    ignored: false,
    notes: 'Called and prayed together. Family is coping well.',
    reminder_sent: true,
    created_at: daysAgo(14),
    updated_at: daysAgo(10),
  },
  {
    id: 'grief_stage_002',
    care_event_id: 'event_002',
    member_id: 'member_002',
    member_name: 'Agus Wijaya',
    member_phone: '+6281234567892',
    campus_id: 'campus_mock_001',
    stage: 'Day 7 - Week 1 Check-in',
    scheduled_date: daysAgo(7),
    completed: true,
    completed_at: daysAgo(6),
    ignored: false,
    notes: 'Visited home. Shared scripture and prayed.',
    reminder_sent: true,
    created_at: daysAgo(14),
    updated_at: daysAgo(6),
  },
  {
    id: 'grief_stage_003',
    care_event_id: 'event_002',
    member_id: 'member_002',
    member_name: 'Agus Wijaya',
    member_phone: '+6281234567892',
    campus_id: 'campus_mock_001',
    stage: 'Day 14 - Two Weeks',
    scheduled_date: daysFromNow(0), // Today!
    completed: false,
    ignored: false,
    reminder_sent: true,
    created_at: daysAgo(14),
    updated_at: daysAgo(14),
  },
  {
    id: 'grief_stage_004',
    care_event_id: 'event_002',
    member_id: 'member_002',
    member_name: 'Agus Wijaya',
    member_phone: '+6281234567892',
    campus_id: 'campus_mock_001',
    stage: 'Day 40 - Month Check-in',
    scheduled_date: daysFromNow(26),
    completed: false,
    ignored: false,
    reminder_sent: false,
    created_at: daysAgo(14),
    updated_at: daysAgo(14),
  },
  {
    id: 'grief_stage_005',
    care_event_id: 'event_002',
    member_id: 'member_002',
    member_name: 'Agus Wijaya',
    member_phone: '+6281234567892',
    campus_id: 'campus_mock_001',
    stage: 'Day 100 - Quarterly',
    scheduled_date: daysFromNow(86),
    completed: false,
    ignored: false,
    reminder_sent: false,
    created_at: daysAgo(14),
    updated_at: daysAgo(14),
  },
  {
    id: 'grief_stage_006',
    care_event_id: 'event_002',
    member_id: 'member_002',
    member_name: 'Agus Wijaya',
    member_phone: '+6281234567892',
    campus_id: 'campus_mock_001',
    stage: '1 Year Memorial',
    scheduled_date: daysFromNow(351),
    completed: false,
    ignored: false,
    reminder_sent: false,
    created_at: daysAgo(14),
    updated_at: daysAgo(14),
  },
];

// ============================================================================
// MOCK FINANCIAL AID SCHEDULES
// ============================================================================

export const mockFinancialAidSchedules: FinancialAidSchedule[] = [
  {
    id: 'aid_schedule_001',
    member_id: 'member_003',
    member_name: 'Maria Tan',
    member_phone: '+6281234567893',
    campus_id: 'campus_mock_001',
    title: 'Education Support - 2 Children',
    aid_type: 'education',
    aid_amount: 2500000,
    frequency: 'monthly',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    day_of_month: 1,
    is_active: true,
    ignored: false,
    ignored_occurrences: [],
    next_occurrence: daysFromNow(15),
    occurrences_completed: 11,
    created_by: mockUser.id,
    notes: 'Tuition for elementary school children',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: daysAgo(30),
  },
  {
    id: 'aid_schedule_002',
    member_id: 'member_004',
    member_name: 'Hendri Susanto',
    member_phone: '+6281234567894',
    campus_id: 'campus_mock_001',
    title: 'Emergency Food Assistance',
    aid_type: 'food',
    aid_amount: 500000,
    frequency: 'weekly',
    start_date: '2024-11-01',
    end_date: '2024-12-31',
    day_of_week: 'Friday',
    is_active: true,
    ignored: false,
    ignored_occurrences: [],
    next_occurrence: daysFromNow(2),
    occurrences_completed: 5,
    created_by: mockUser.id,
    notes: 'Weekly groceries support until finds new job',
    created_at: '2024-11-01T00:00:00Z',
    updated_at: daysAgo(7),
  },
  {
    id: 'aid_schedule_003',
    member_id: 'member_006',
    member_name: 'Robert Halim',
    member_phone: '+6281234567896',
    campus_id: 'campus_mock_001',
    title: 'Medical Treatment Support',
    aid_type: 'medical',
    aid_amount: 5000000,
    frequency: 'one_time',
    start_date: daysAgo(30),
    is_active: false,
    ignored: false,
    ignored_occurrences: [],
    occurrences_completed: 1,
    created_by: mockUser.id,
    notes: 'One-time support for surgery costs',
    created_at: daysAgo(35),
    updated_at: daysAgo(30),
  },
];

// ============================================================================
// MOCK DASHBOARD REMINDERS
// ============================================================================

export const mockDashboardReminders: DashboardReminders = {
  birthdays_today: [
    {
      type: 'birthday',
      member_id: 'member_001',
      member_name: 'Siti Rahayu',
      member_phone: '+6281234567891',
      member_age: 34,
      event_id: 'event_001',
      scheduled_date: daysFromNow(0),
    },
  ],
  upcoming_birthdays: [
    {
      type: 'birthday',
      member_id: 'member_005',
      member_name: 'Linda Permata',
      member_phone: '+6281234567895',
      member_age: 25,
      scheduled_date: daysFromNow(19), // Dec 25
    },
  ],
  grief_today: [
    {
      type: 'grief_support',
      member_id: 'member_002',
      member_name: 'Agus Wijaya',
      member_phone: '+6281234567892',
      stage_id: 'grief_stage_003',
      stage: 'Day 14 - Two Weeks',
      scheduled_date: daysFromNow(0),
      title: 'Grief Support Follow-up',
    },
  ],
  accident_followup: [
    {
      type: 'accident_followup',
      member_id: 'member_005',
      member_name: 'Linda Permata',
      member_phone: '+6281234567895',
      stage_id: 'accident_001',
      stage: 'First Follow-up',
      scheduled_date: daysFromNow(0),
      title: 'Hospital Recovery Check',
    },
  ],
  at_risk_members: [
    {
      type: 'at_risk',
      member_id: 'member_002',
      member_name: 'Agus Wijaya',
      member_phone: '+6281234567892',
      days_since_last_contact: 45,
    },
    {
      type: 'at_risk',
      member_id: 'member_006',
      member_name: 'Robert Halim',
      member_phone: '+6281234567896',
      days_since_last_contact: 75,
    },
  ],
  disconnected_members: [
    {
      type: 'disconnected',
      member_id: 'member_004',
      member_name: 'Hendri Susanto',
      member_phone: '+6281234567894',
      days_since_last_contact: 120,
    },
  ],
  financial_aid_due: [
    {
      type: 'financial_aid',
      member_id: 'member_004',
      member_name: 'Hendri Susanto',
      member_phone: '+6281234567894',
      aid_amount: 500000,
      aid_type: 'food',
      title: 'Weekly Food Assistance',
      scheduled_date: daysFromNow(2),
    },
  ],
  ai_suggestions: [],
  total_tasks: 8,
  total_members: 8,
  cache_version: 'mock_v1',
};

// ============================================================================
// MOCK ACCIDENT FOLLOWUPS
// ============================================================================

export const mockAccidentFollowups = [
  {
    id: 'accident_001',
    care_event_id: 'event_004',
    member_id: 'member_005',
    member_name: 'Linda Permata',
    member_phone: '+6281234567895',
    campus_id: 'campus_mock_001',
    stage: 'first_followup' as const,
    scheduled_date: daysFromNow(0),
    completed: false,
    ignored: false,
    notes: undefined,
    created_at: daysAgo(3),
    updated_at: daysAgo(3),
  },
  {
    id: 'accident_002',
    care_event_id: 'event_004',
    member_id: 'member_005',
    member_name: 'Linda Permata',
    member_phone: '+6281234567895',
    campus_id: 'campus_mock_001',
    stage: 'second_followup' as const,
    scheduled_date: daysFromNow(4),
    completed: false,
    ignored: false,
    notes: undefined,
    created_at: daysAgo(3),
    updated_at: daysAgo(3),
  },
  {
    id: 'accident_003',
    care_event_id: 'event_004',
    member_id: 'member_005',
    member_name: 'Linda Permata',
    member_phone: '+6281234567895',
    campus_id: 'campus_mock_001',
    stage: 'final_followup' as const,
    scheduled_date: daysFromNow(11),
    completed: false,
    ignored: false,
    notes: undefined,
    created_at: daysAgo(3),
    updated_at: daysAgo(3),
  },
];

export default {
  MOCK_MODE_ENABLED,
  simulateApiDelay,
  mockUser,
  mockMembers,
  mockMemberListItems,
  mockCareEvents,
  mockGriefStages,
  mockFinancialAidSchedules,
  mockDashboardReminders,
  mockAccidentFollowups,
};
