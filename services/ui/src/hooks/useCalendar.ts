import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { calendarApi } from '../api/calendar'

export function useCalendarStatus() {
  return useQuery({
    queryKey: ['calendar', 'status'],
    queryFn: calendarApi.getStatus,
  })
}

export function useConnectCalendar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (authCode: string) => calendarApi.connect(authCode),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
    },
  })
}

export function useSyncCalendar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => calendarApi.sync(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
    },
  })
}

export function useDisconnectCalendar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (syncId: string) => calendarApi.disconnect(syncId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
    },
  })
}
