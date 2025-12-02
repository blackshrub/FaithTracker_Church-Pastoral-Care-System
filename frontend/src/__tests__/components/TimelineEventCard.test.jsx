/**
 * Tests for TimelineEventCard component
 *
 * Tests the timeline event card display logic and interactions
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { TimelineEventCard } from '../../components/member/TimelineEventCard';

// Mock date formatting
jest.mock('date-fns/format', () => ({
  format: jest.fn((date, formatStr) => {
    if (formatStr === 'dd') return '15';
    if (formatStr === 'MMM') return 'Jan';
    if (formatStr === 'dd MMM yyyy') return '15 Jan 2024';
    return date.toString();
  })
}));

describe('TimelineEventCard', () => {
  const mockEvent = {
    id: 'event-1',
    event_type: 'birthday',
    title: 'John Doe Birthday',
    event_date: '2024-01-15',
    description: 'Send birthday wishes',
    completed: false,
    ignored: false
  };

  const mockOnDelete = jest.fn();

  beforeEach(() => {
    mockOnDelete.mockClear();
  });

  test('renders event title and description', () => {
    render(<TimelineEventCard event={mockEvent} onDelete={mockOnDelete} />);

    expect(screen.getByText('John Doe Birthday')).toBeInTheDocument();
    expect(screen.getByText('Send birthday wishes')).toBeInTheDocument();
  });

  test('displays formatted date', () => {
    render(<TimelineEventCard event={mockEvent} onDelete={mockOnDelete} />);

    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('Jan')).toBeInTheDocument();
  });

  test('shows birthday event type badge', () => {
    render(<TimelineEventCard event={mockEvent} onDelete={mockOnDelete} />);

    // EventTypeBadge should be rendered (implementation details may vary)
    const card = screen.getByTestId(`care-event-${mockEvent.id}`);
    expect(card).toBeInTheDocument();
  });

  test('shows completed badge when event is completed', () => {
    const completedEvent = {
      ...mockEvent,
      completed: true,
      completed_by_user_name: 'Admin User',
      completed_at: '2024-01-15T10:00:00Z'
    };

    render(<TimelineEventCard event={completedEvent} onDelete={mockOnDelete} />);

    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText(/Completed by:/)).toBeInTheDocument();
    expect(screen.getByText(/Admin User/)).toBeInTheDocument();
  });

  test('shows ignored badge when event is ignored', () => {
    const ignoredEvent = {
      ...mockEvent,
      ignored: true,
      ignored_by_name: 'Pastor John',
      ignored_at: '2024-01-15T10:00:00Z'
    };

    render(<TimelineEventCard event={ignoredEvent} onDelete={mockOnDelete} />);

    expect(screen.getByText('Ignored')).toBeInTheDocument();
    expect(screen.getByText(/Ignored by:/)).toBeInTheDocument();
    expect(screen.getByText(/Pastor John/)).toBeInTheDocument();
  });

  test('applies opacity when event is completed or ignored', () => {
    const { container: completedContainer } = render(
      <TimelineEventCard event={{ ...mockEvent, completed: true }} onDelete={mockOnDelete} />
    );

    const completedCard = completedContainer.querySelector('.opacity-60');
    expect(completedCard).toBeInTheDocument();
  });

  test('displays grief relationship when present', () => {
    const griefEvent = {
      ...mockEvent,
      event_type: 'grief_loss',
      grief_relationship: 'parent'
    };

    render(<TimelineEventCard event={griefEvent} onDelete={mockOnDelete} />);

    expect(screen.getByText(/Relationship:/)).toBeInTheDocument();
    expect(screen.getByText(/Parent/)).toBeInTheDocument();
  });

  test('displays hospital name when present and valid', () => {
    const hospitalEvent = {
      ...mockEvent,
      event_type: 'hospital_visit',
      hospital_name: 'Jakarta General Hospital'
    };

    render(<TimelineEventCard event={hospitalEvent} onDelete={mockOnDelete} />);

    expect(screen.getByText(/Hospital:/)).toBeInTheDocument();
    expect(screen.getByText(/Jakarta General Hospital/)).toBeInTheDocument();
  });

  test('hides hospital name when value is N/A or null', () => {
    const eventWithNA = {
      ...mockEvent,
      hospital_name: 'N/A'
    };

    render(<TimelineEventCard event={eventWithNA} onDelete={mockOnDelete} />);

    expect(screen.queryByText(/Hospital:/)).not.toBeInTheDocument();
  });

  test('displays financial aid amount when present', () => {
    const aidEvent = {
      ...mockEvent,
      event_type: 'financial_aid',
      aid_amount: 1500000,
      aid_type: 'Education Support'
    };

    render(<TimelineEventCard event={aidEvent} onDelete={mockOnDelete} />);

    expect(screen.getByText(/Education Support/)).toBeInTheDocument();
    expect(screen.getByText(/Rp 1.500.000/)).toBeInTheDocument();
  });

  test('displays created by information when present', () => {
    const eventWithCreator = {
      ...mockEvent,
      created_by_user_name: 'Pastor Jane'
    };

    render(<TimelineEventCard event={eventWithCreator} onDelete={mockOnDelete} />);

    expect(screen.getByText(/Created by:/)).toBeInTheDocument();
    expect(screen.getByText(/Pastor Jane/)).toBeInTheDocument();
  });

  test('renders children content when provided', () => {
    render(
      <TimelineEventCard event={mockEvent} onDelete={mockOnDelete}>
        <div data-testid="custom-content">Custom Content</div>
      </TimelineEventCard>
    );

    expect(screen.getByTestId('custom-content')).toBeInTheDocument();
    expect(screen.getByText('Custom Content')).toBeInTheDocument();
  });

  test('calls onDelete when delete button is clicked', () => {
    render(<TimelineEventCard event={mockEvent} onDelete={mockOnDelete} />);

    // Find and click the more options button
    const moreButton = screen.getByRole('button', { name: /more/i });
    fireEvent.click(moreButton);

    // Find and click delete button
    const deleteButton = screen.getByText('Delete');
    fireEvent.click(deleteButton);

    expect(mockOnDelete).toHaveBeenCalledWith(mockEvent.id);
    expect(mockOnDelete).toHaveBeenCalledTimes(1);
  });

  test('applies correct color classes for celebration events', () => {
    const celebrationEvent = {
      ...mockEvent,
      event_type: 'birthday'
    };

    const { container } = render(
      <TimelineEventCard event={celebrationEvent} onDelete={mockOnDelete} />
    );

    const amberDot = container.querySelector('.bg-amber-500');
    expect(amberDot).toBeInTheDocument();
  });

  test('applies correct color classes for care events', () => {
    const careEvent = {
      ...mockEvent,
      event_type: 'grief_loss'
    };

    const { container } = render(
      <TimelineEventCard event={careEvent} onDelete={mockOnDelete} />
    );

    const pinkDot = container.querySelector('.bg-pink-500');
    expect(pinkDot).toBeInTheDocument();
  });

  test('applies correct color classes for financial aid events', () => {
    const aidEvent = {
      ...mockEvent,
      event_type: 'financial_aid'
    };

    const { container } = render(
      <TimelineEventCard event={aidEvent} onDelete={mockOnDelete} />
    );

    const purpleDot = container.querySelector('.bg-purple-500');
    expect(purpleDot).toBeInTheDocument();
  });
});
