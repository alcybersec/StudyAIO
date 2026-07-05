import { api } from './client'
import type { GlobalSearchResponse } from '../types'

export const searchApi = {
  /** GET /api/search — global search across courses, summaries, flashcards and chats. */
  search: (q: string, limit = 10) =>
    api.get<GlobalSearchResponse>(`/search?q=${encodeURIComponent(q)}&limit=${limit}`),
}
