import { describe, it, expect } from 'vitest'
import { screen, within, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { AdminLogsPage } from './AdminLogsPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { LogEntry } from '@/api/admin'

function buildLog(overrides: Partial<LogEntry> = {}): LogEntry {
  return {
    id: 'l1',
    timestamp: '2026-05-01T10:00:00Z',
    level: 'ERROR',
    module: 'app.main',
    message: 'Something failed',
    source: 'app',
    ...overrides,
  }
}

const defaultStats = { errors_24h: 3, warnings_24h: 5, total_logs: 100 }
const defaultSources = {
  sources: [
    { name: 'app', label: 'Application', available: true },
    { name: 'celery', label: 'Celery', available: true },
  ],
}

function mockLogsBase() {
  server.use(
    http.get('*/admin/logs/stats', () => HttpResponse.json(defaultStats)),
    http.get('*/admin/logs/sources', () => HttpResponse.json(defaultSources)),
  )
}

function logsResponse(logs: LogEntry[], totalPages = 1, total = logs.length) {
  return {
    logs,
    total,
    page: 1,
    page_size: 50,
    total_pages: totalPages,
  }
}

describe('AdminLogsPage', () => {
  it('shows a loading spinner while logs are being fetched', () => {
    mockLogsBase()
    server.use(
      http.get('*/admin/logs', async () => {
        await delay('infinite')
        return HttpResponse.json(logsResponse([]))
      }),
    )

    renderWithProviders(<AdminLogsPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders the logs and the statistics', async () => {
    mockLogsBase()
    server.use(
      http.get('*/admin/logs', () => HttpResponse.json(logsResponse([buildLog()]))),
    )

    renderWithProviders(<AdminLogsPage />)

    expect(
      await screen.findByRole('heading', { name: 'System Logs' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Errors (24h)')).toBeInTheDocument()
    expect(screen.getByText('Something failed')).toBeInTheDocument()
    expect(
      within(screen.getByText('Something failed').closest('tr') as HTMLElement).getByText(
        'ERROR',
      ),
    ).toBeInTheDocument()
  })

  it('shows an error toast when logs fail to load', async () => {
    mockLogsBase()
    server.use(
      http.get('*/admin/logs', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    )

    renderWithProviders(<AdminLogsPage />)

    expect(await screen.findByText('Error Loading Logs')).toBeInTheDocument()
  })

  it('shows the empty state when there are no logs', async () => {
    mockLogsBase()
    server.use(
      http.get('*/admin/logs', () => HttpResponse.json(logsResponse([]))),
    )

    renderWithProviders(<AdminLogsPage />)

    expect(await screen.findByText('No logs found')).toBeInTheDocument()
  })

  it('filters the logs by level', async () => {
    mockLogsBase()
    server.use(
      http.get('*/admin/logs', ({ request }) => {
        const level = new URL(request.url).searchParams.get('level')
        if (level === 'INFO') {
          return HttpResponse.json(
            logsResponse([
              buildLog({ id: 'l2', level: 'INFO', message: 'Info message' }),
            ]),
          )
        }
        return HttpResponse.json(logsResponse([buildLog()]))
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminLogsPage />)
    await screen.findByText('Something failed')

    await user.selectOptions(screen.getByLabelText('Log Level'), 'INFO')

    expect(await screen.findByText('Info message')).toBeInTheDocument()
    expect(screen.queryByText('Something failed')).not.toBeInTheDocument()
  })

  it('paginates to the next page of logs', async () => {
    mockLogsBase()
    server.use(
      http.get('*/admin/logs', ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get('page') ?? '1')
        return HttpResponse.json(
          logsResponse(
            [buildLog({ id: `p${page}`, message: `Log on page ${page}` })],
            2,
            100,
          ),
        )
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminLogsPage />)
    await screen.findByText('Log on page 1')

    await user.click(screen.getByRole('button', { name: 'Next page' }))

    expect(await screen.findByText('Log on page 2')).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByText(/Showing page 2 of 2/)).toBeInTheDocument(),
    )
  })
})
