/**
 * Normalized data schemas shared between the API and web.
 * These mirror packages/shared/python/signal_hub_shared/models.py.
 * When a field changes in either place, update the other.
 */

import { z } from "zod";

export const ItemSource = z.enum([
  "gmail",
  "google_calendar",
  "notion",
  "whatsapp",
  "linkedin",
  "imessage",
]);
export type ItemSource = z.infer<typeof ItemSource>;

export const MessageSchema = z.object({
  external_id: z.string(),
  source: ItemSource,
  sender: z.string(),
  subject: z.string().nullable().optional(),
  body_preview: z.string(),
  is_read: z.boolean().default(false),
  received_at: z.string().datetime(),
  thread_id: z.string().nullable().optional(),
  raw_json: z.record(z.unknown()).nullable().optional(),
});
export type Message = z.infer<typeof MessageSchema>;

export const EventSchema = z.object({
  external_id: z.string(),
  source: ItemSource,
  title: z.string(),
  description: z.string().nullable().optional(),
  start_at: z.string().datetime(),
  end_at: z.string().datetime(),
  location: z.string().nullable().optional(),
  attendees: z.array(z.string()).default([]),
  meeting_url: z.string().nullable().optional(),
  raw_json: z.record(z.unknown()).nullable().optional(),
});
export type Event = z.infer<typeof EventSchema>;

export const TaskSchema = z.object({
  external_id: z.string(),
  source: ItemSource,
  title: z.string(),
  description: z.string().nullable().optional(),
  is_done: z.boolean().default(false),
  due_at: z.string().datetime().nullable().optional(),
  priority: z.string().nullable().optional(),
  raw_json: z.record(z.unknown()).nullable().optional(),
});
export type Task = z.infer<typeof TaskSchema>;

export const NotificationSchema = z.object({
  external_id: z.string(),
  source: ItemSource,
  title: z.string(),
  body: z.string().nullable().optional(),
  is_read: z.boolean().default(false),
  received_at: z.string().datetime(),
  raw_json: z.record(z.unknown()).nullable().optional(),
});
export type Notification = z.infer<typeof NotificationSchema>;
