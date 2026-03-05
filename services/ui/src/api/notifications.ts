import { api } from './client'
import type {
  NotificationPreferenceItem,
  NotificationPreferencesResponse,
  TelegramLinkResponse,
  TelegramStatusResponse,
  TestNotificationResponse,
} from '../types'

export const notificationsApi = {
  getPreferences: () =>
    api.get<NotificationPreferencesResponse>('/notifications/preferences'),

  updatePreferences: (preferences: NotificationPreferenceItem[]) =>
    api.put<NotificationPreferencesResponse>('/notifications/preferences', {
      preferences,
    }),

  generateTelegramLink: () =>
    api.post<TelegramLinkResponse>('/notifications/telegram/link'),

  unlinkTelegram: () =>
    api.delete<TelegramStatusResponse>('/notifications/telegram/unlink'),

  sendTest: (channel: string) =>
    api.post<TestNotificationResponse>('/notifications/test', { channel }),
}
