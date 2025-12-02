/**
 * Tests for MemberProfileHeader component
 *
 * Tests the member profile header display, interactions, and responsive behavior
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { MemberProfileHeader } from '../../components/member/MemberProfileHeader';

// Mock react-i18next
jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => {
      const translations = {
        'last_contact': 'Last Contact',
        'add_care_event': 'Add Care Event'
      };
      return translations[key] || key;
    }
  })
}));

// Mock date formatting
jest.mock('date-fns/format', () => ({
  format: jest.fn((date, formatStr) => {
    if (formatStr === 'dd MMM yyyy') return '15 Jan 2024';
    return date.toString();
  })
}));

// Mock child components
jest.mock('@/components/MemberAvatar', () => ({
  MemberAvatar: ({ member, size, className }) => (
    <div data-testid="member-avatar" data-size={size} className={className}>
      {member.name}
    </div>
  )
}));

jest.mock('@/components/EngagementBadge', () => ({
  EngagementBadge: ({ status, days }) => (
    <div data-testid="engagement-badge" data-status={status} data-days={days}>
      {status}
    </div>
  )
}));

// Wrapper for router context
const renderWithRouter = (ui, { route = '/' } = {}) => {
  window.history.pushState({}, 'Test page', route);
  return render(ui, { wrapper: BrowserRouter });
};

describe('MemberProfileHeader', () => {
  const mockMember = {
    id: 'member-1',
    name: 'John Doe',
    phone: '+6281234567890',
    email: 'john@test.com',
    engagement_status: 'active',
    days_since_last_contact: 5,
    last_contact_date: '2024-01-15'
  };

  const mockOnAddCareEvent = jest.fn();

  beforeEach(() => {
    mockOnAddCareEvent.mockClear();
  });

  test('renders member name', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });

  test('renders member phone number with tel link', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const phoneLink = screen.getByRole('link', { name: /\+6281234567890/i });
    expect(phoneLink).toBeInTheDocument();
    expect(phoneLink).toHaveAttribute('href', 'tel:+6281234567890');
  });

  test('hides phone number when not provided', () => {
    const memberWithoutPhone = {
      ...mockMember,
      phone: null
    };

    renderWithRouter(
      <MemberProfileHeader member={memberWithoutPhone} onAddCareEvent={mockOnAddCareEvent} />
    );

    expect(screen.queryByRole('link', { name: /tel:/i })).not.toBeInTheDocument();
  });

  test('renders MemberAvatar component', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const avatar = screen.getByTestId('member-avatar');
    expect(avatar).toBeInTheDocument();
    expect(avatar).toHaveAttribute('data-size', 'xl');
  });

  test('renders EngagementBadge with correct status and days', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const badge = screen.getByTestId('engagement-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute('data-status', 'active');
    expect(badge).toHaveAttribute('data-days', '5');
  });

  test('displays last contact date when available', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    expect(screen.getByText(/Last Contact:/)).toBeInTheDocument();
    expect(screen.getByText(/15 Jan 2024/)).toBeInTheDocument();
  });

  test('hides last contact date when not available', () => {
    const memberWithoutLastContact = {
      ...mockMember,
      last_contact_date: null
    };

    renderWithRouter(
      <MemberProfileHeader member={memberWithoutLastContact} onAddCareEvent={mockOnAddCareEvent} />
    );

    expect(screen.queryByText(/Last Contact:/)).not.toBeInTheDocument();
  });

  test('renders back button with default link', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const backButton = screen.getByRole('button', { name: /back to members/i });
    expect(backButton).toBeInTheDocument();

    // Check that it's wrapped in a Link with default href
    expect(backButton.closest('a')).toHaveAttribute('href', '/members');
  });

  test('renders back button with custom link', () => {
    renderWithRouter(
      <MemberProfileHeader
        member={mockMember}
        onAddCareEvent={mockOnAddCareEvent}
        backLink="/dashboard"
      />
    );

    const backButton = screen.getByRole('button', { name: /back to members/i });
    expect(backButton.closest('a')).toHaveAttribute('href', '/dashboard');
  });

  test('renders add care event button', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const addButton = screen.getByTestId('add-care-event-button');
    expect(addButton).toBeInTheDocument();
    expect(addButton).toHaveTextContent('Add Care Event');
  });

  test('calls onAddCareEvent when add button is clicked', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const addButton = screen.getByTestId('add-care-event-button');
    fireEvent.click(addButton);

    expect(mockOnAddCareEvent).toHaveBeenCalledTimes(1);
  });

  test('returns null when member is null', () => {
    const { container } = renderWithRouter(
      <MemberProfileHeader member={null} onAddCareEvent={mockOnAddCareEvent} />
    );

    expect(container.firstChild).toBeNull();
  });

  test('returns null when member is undefined', () => {
    const { container } = renderWithRouter(
      <MemberProfileHeader member={undefined} onAddCareEvent={mockOnAddCareEvent} />
    );

    expect(container.firstChild).toBeNull();
  });

  test('handles member with minimal data', () => {
    const minimalMember = {
      id: 'member-2',
      name: 'Jane Smith'
    };

    renderWithRouter(
      <MemberProfileHeader member={minimalMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /tel:/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Last Contact:/)).not.toBeInTheDocument();
  });

  test('applies correct responsive classes', () => {
    const { container } = renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    // Check for responsive flex classes
    const profileSection = container.querySelector('.flex.flex-col.sm\\:flex-row');
    expect(profileSection).toBeInTheDocument();
  });

  test('phone link has correct styling classes', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const phoneLink = screen.getByRole('link', { name: /\+6281234567890/i });
    expect(phoneLink).toHaveClass('text-teal-600');
    expect(phoneLink).toHaveClass('hover:text-teal-700');
  });

  test('add care event button has correct styling', () => {
    renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const addButton = screen.getByTestId('add-care-event-button');
    expect(addButton).toHaveClass('bg-teal-500');
    expect(addButton).toHaveClass('hover:bg-teal-600');
  });

  test('displays engagement badge before last contact date', () => {
    const { container } = renderWithRouter(
      <MemberProfileHeader member={mockMember} onAddCareEvent={mockOnAddCareEvent} />
    );

    const badge = screen.getByTestId('engagement-badge');
    const lastContactText = screen.getByText(/Last Contact:/);

    // Badge should appear in DOM before last contact text
    expect(badge.compareDocumentPosition(lastContactText)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });
});
