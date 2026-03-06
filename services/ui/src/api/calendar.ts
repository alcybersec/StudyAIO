import { api } from './client'
import type { CalendarConnectResponse, CalendarSyncResult, CalendarSyncStatusResponse } from '../types'

export const calendarApi = {
  getStatus: () => api.get<CalendarSyncStatusResponse>('/calendar/status'),

  connect: (authCode: string) =>
    api.post<CalendarConnectResponse>('/calendar/connect', { auth_code: authCode }),

  sync: () => api.post<CalendarSyncResult>('/calendar/sync'),

  disconnect: (syncId: string) => api.delete(`/calendar/disconnect/${syncId}`),
}
