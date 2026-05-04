import { http, HttpResponse } from 'msw'
import type { User } from '@/types'

export const defaultUser: User = {
  id: 'test-user-id',
  email: 'test@example.com',
  is_admin: false,
  display_name: null,
  preferred_language: 'en',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

export const handlers = [
  http.get('*/auth/me', () => HttpResponse.json(defaultUser)),
  http.get('*/notifications/unread-count', () => HttpResponse.json({ unread_count: 0 })),
]
