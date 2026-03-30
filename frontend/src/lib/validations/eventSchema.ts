/**
 * Event Form Validation Schemas
 * Zod schemas for validating care event forms
 */

import { z } from 'zod';
import type { EventType } from '@/types';

// Base event schema with common fields
const baseEventSchema = z.object({
  event_type: z.string().min(1, 'Event type is required'),
  event_date: z.string().min(1, 'Event date is required'),
  description: z.string().optional(),
});

// Birthday event schema
export const birthdayEventSchema = baseEventSchema.extend({
  event_type: z.literal('birthday'),
});

// Grief/Loss event schema
export const griefEventSchema = baseEventSchema.extend({
  event_type: z.literal('grief_loss'),
  grief_relationship: z.string().min(1, 'Relationship to deceased is required'),
});

// Hospital visit event schema
export const hospitalEventSchema = baseEventSchema.extend({
  event_type: z.literal('hospital_visit'),
  hospital_name: z.string().min(1, 'Hospital name is required'),
});

// Financial aid event schema
export const financialAidEventSchema = baseEventSchema.extend({
  event_type: z.literal('financial_aid'),
  aid_amount: z.number().positive('Aid amount must be greater than 0'),
  aid_type: z.string().optional(),
});

// Regular contact event schema
export const regularContactSchema = baseEventSchema.extend({
  event_type: z.literal('regular_contact'),
});

// Infer types from Zod schemas
export type BaseEventData = z.infer<typeof baseEventSchema>;
export type BirthdayEventData = z.infer<typeof birthdayEventSchema>;
export type GriefEventData = z.infer<typeof griefEventSchema>;
export type HospitalEventData = z.infer<typeof hospitalEventSchema>;
export type FinancialAidEventData = z.infer<typeof financialAidEventSchema>;
export type RegularContactData = z.infer<typeof regularContactSchema>;

type EventSchema =
  | typeof birthdayEventSchema
  | typeof griefEventSchema
  | typeof hospitalEventSchema
  | typeof financialAidEventSchema
  | typeof regularContactSchema
  | typeof baseEventSchema;

// Dynamic schema based on event type
export const createEventSchema = (eventType: EventType | string): EventSchema => {
  switch (eventType) {
    case 'birthday':
      return birthdayEventSchema;
    case 'grief_loss':
      return griefEventSchema;
    case 'hospital_visit':
      return hospitalEventSchema;
    case 'financial_aid':
      return financialAidEventSchema;
    case 'regular_contact':
      return regularContactSchema;
    default:
      return baseEventSchema;
  }
};

interface ValidationSuccess {
  success: true;
  data: Record<string, unknown>;
  errors?: undefined;
}

interface ValidationFailure {
  success: false;
  errors: Record<string, string>;
  data?: undefined;
}

type ValidationResult = ValidationSuccess | ValidationFailure;

/**
 * Validate event data against appropriate schema
 * @param data - Event form data
 * @returns Validation result with success flag and either data or errors
 */
export const validateEventData = (data: Record<string, unknown>): ValidationResult => {
  const schema = createEventSchema(data.event_type as string);
  const result = schema.safeParse(data);

  if (!result.success) {
    const errors: Record<string, string> = {};
    result.error.errors.forEach((err) => {
      const path = err.path.join('.');
      errors[path] = err.message;
    });
    return { success: false, errors };
  }

  return { success: true, data: result.data as Record<string, unknown> };
};

// Member selection validation
export const memberSelectionSchema = z.object({
  member_ids: z.array(z.string()).min(1, 'Please select at least one member'),
});

interface MemberValidationSuccess {
  success: true;
  error?: undefined;
}

interface MemberValidationFailure {
  success: false;
  error: string;
}

type MemberValidationResult = MemberValidationSuccess | MemberValidationFailure;

/**
 * Validate that at least one member is selected
 * @param memberIds - Array of member IDs
 * @returns Validation result
 */
export const validateMemberSelection = (memberIds: string[] | null | undefined): MemberValidationResult => {
  if (!memberIds || memberIds.length === 0) {
    return { success: false, error: 'Please select at least one member' };
  }
  return { success: true };
};
