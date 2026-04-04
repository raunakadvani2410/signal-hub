// Re-export all shared types so app code imports from one place.
export type {
  Event,
  IntegrationConfig,
  IntegrationStatus,
  ItemSource,
  Message,
  Notification,
  Task,
} from "signal-hub-shared";

export {
  IntegrationConfigSchema,
  MessageSchema,
  EventSchema,
  TaskSchema,
  NotificationSchema,
} from "signal-hub-shared";
