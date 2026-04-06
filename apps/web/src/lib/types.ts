// Re-export all shared types so app code imports from one place.
export type {
  Event,
  FeedItem,
  IntegrationConfig,
  IntegrationStatus,
  ItemSource,
  ItemType,
  Message,
  Notification,
  Task,
} from "signal-hub-shared";

export {
  FeedItemSchema,
  IntegrationConfigSchema,
  ItemSource,
  ItemType,
  MessageSchema,
  EventSchema,
  TaskSchema,
  NotificationSchema,
} from "signal-hub-shared";
