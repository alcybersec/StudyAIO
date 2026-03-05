import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { notificationsApi } from '../api/notifications'
import type { NotificationPreferenceItem } from '../types'

export function useNotificationPreferences() {
  return useQuery({
    queryKey: ['notificationPreferences'],
    queryFn: notificationsApi.getPreferences,
  })
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (preferences: NotificationPreferenceItem[]) =>
      notificationsApi.updatePreferences(preferences),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationPreferences'] })
    },
  })
}

export function useTelegramLink() {
  return useMutation({
    mutationFn: notificationsApi.generateTelegramLink,
  })
}

export function useUnlinkTelegram() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: notificationsApi.unlinkTelegram,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationPreferences'] })
    },
  })
}

export function useTestNotification() {
  return useMutation({
    mutationFn: (channel: string) => notificationsApi.sendTest(channel),
  })
}
