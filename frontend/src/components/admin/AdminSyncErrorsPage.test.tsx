import { describe, it, expect } from 'vitest'
import { screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import i18next from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { AdminSyncErrorsPage } from './AdminSyncErrorsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { AdminSyncError } from '@/api/adminSyncErrors'
import enAdminSyncErrors from '@/i18n/locales/en/adminSyncErrors.json'
import enSyncErrors from '@/i18n/locales/en/syncErrors.json'

// The global i18n instance is initialised in main.tsx (not loaded by tests),
// so build a dedicated, synchronously-initialised instance with the bundled
// English resources and disable suspense for deterministic rendering.
const testI18n = i18next.createInstance()
testI18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  ns: ['adminSyncErrors', 'syncErrors', 'translation'],
  defaultNS: 'translation',
  resources: {
    en: {
      adminSyncErrors: enAdminSyncErrors,
      syncErrors: enSyncErrors,
      translation: {},
    },
  },
  react: { useSuspense: false },
  interpolation: { escapeValue: false },
})

function renderPage() {
  return renderWithProviders(
    <I18nextProvider i18n={testI18n}>
      <AdminSyncErrorsPage />
    </I18nextProvider>,
  )
}

function buildError(overrides: Partial<AdminSyncError> = {}): AdminSyncError {
  return {
    id: 'se-1',
    mailbox_id: 'mbx-123456789',
    sync_history_id: null,
    provider_message_id: null,
    subject: 'Invoice #42',
    sender: 'billing@acme.com',
    error_type: 'extraction_failed',
    error_message: 'Extraction blew up',
    severity: 'high',
    status: 'pending',
    resolution: null,
    retry_count: 0,
    last_retry_at: null,
    created_at: '2026-05-01T10:00:00Z',
    updated_at: '2026-05-01T10:00:00Z',
    stack_trace: 'Traceback (most recent call last): ...',
    raw_payload: { foo: 'bar' },
    resolved_at: null,
    resolved_by_id: null,
    ...overrides,
  }
}

function listResponse(items: AdminSyncError[], total = items.length) {
  return { items, total, page: 1, page_size: 20 }
}

function rowFor(text: string) {
  return within(screen.getByText(text).closest('tr') as HTMLElement)
}

describe('AdminSyncErrorsPage', () => {
  it('shows a loading spinner while errors are being fetched', () => {
    server.use(
      http.get('*/admin/sync-errors', async () => {
        await delay('infinite')
        return HttpResponse.json(listResponse([]))
      }),
    )

    renderPage()

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the sync errors', async () => {
    server.use(
      http.get('*/admin/sync-errors', () =>
        HttpResponse.json(listResponse([buildError()])),
      ),
    )

    renderPage()

    // The heading renders before data loads; wait for a data-dependent row.
    await screen.findByText('billing@acme.com')
    expect(
      screen.getByRole('heading', { name: 'Sync errors (all users)' }),
    ).toBeInTheDocument()
    expect(screen.getByText('1 errors total')).toBeInTheDocument()
    const row = rowFor('billing@acme.com')
    expect(row.getByText('extraction_failed')).toBeInTheDocument()
    expect(row.getByText('Pending')).toBeInTheDocument()
    expect(row.getByText('High')).toBeInTheDocument()
  })

  it('shows the empty state when there are no errors', async () => {
    server.use(
      http.get('*/admin/sync-errors', () => HttpResponse.json(listResponse([]))),
    )

    renderPage()

    expect(
      await screen.findByText('No sync errors match the current filters.'),
    ).toBeInTheDocument()
  })

  it('filters the errors by severity', async () => {
    server.use(
      http.get('*/admin/sync-errors', ({ request }) => {
        const severity = new URL(request.url).searchParams.get('severity')
        if (severity === 'high') {
          return HttpResponse.json(
            listResponse([
              buildError({ id: 'se-2', sender: 'high-only@acme.com' }),
            ]),
          )
        }
        return HttpResponse.json(listResponse([buildError()]))
      }),
    )
    const user = userEvent.setup()

    renderPage()
    await screen.findByText('billing@acme.com')

    await user.selectOptions(screen.getByLabelText('Severity'), 'high')

    expect(await screen.findByText('high-only@acme.com')).toBeInTheDocument()
    expect(screen.queryByText('billing@acme.com')).not.toBeInTheDocument()
  })

  it('opens the detail drawer when a row is clicked', async () => {
    server.use(
      http.get('*/admin/sync-errors', () =>
        HttpResponse.json(listResponse([buildError()])),
      ),
      http.get('*/admin/sync-errors/se-1', () =>
        HttpResponse.json(buildError()),
      ),
    )
    const user = userEvent.setup()

    renderPage()
    await user.click(await screen.findByText('billing@acme.com'))

    const drawer = within(await screen.findByRole('dialog'))
    expect(drawer.getByText('Sync error detail')).toBeInTheDocument()
    expect(drawer.getByText('Extraction blew up')).toBeInTheDocument()
    expect(
      drawer.getByText('Traceback (most recent call last): ...'),
    ).toBeInTheDocument()
  })

  it('marks a sync error as resolved from the drawer', async () => {
    let resolvedId: string | null = null
    server.use(
      http.get('*/admin/sync-errors', () =>
        HttpResponse.json(listResponse([buildError()])),
      ),
      http.get('*/admin/sync-errors/se-1', () =>
        HttpResponse.json(buildError()),
      ),
      http.post('*/admin/sync-errors/se-1/resolve', () => {
        resolvedId = 'se-1'
        return HttpResponse.json(
          buildError({ status: 'resolved', resolved_at: '2026-05-02T00:00:00Z' }),
        )
      }),
    )
    const user = userEvent.setup()

    renderPage()
    await user.click(await screen.findByText('billing@acme.com'))

    const drawer = within(await screen.findByRole('dialog'))
    await user.click(await drawer.findByRole('button', { name: 'Mark resolved' }))

    expect(
      await screen.findByText('Sync error marked as resolved.'),
    ).toBeInTheDocument()
    expect(resolvedId).toBe('se-1')
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
  })
})
