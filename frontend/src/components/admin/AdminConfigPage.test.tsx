import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse, delay } from 'msw'
import { AdminConfigPage } from './AdminConfigPage'
import { renderWithProviders } from '@/test/renderWithProviders'
import { server } from '@/test/server'
import type { AdminSetting, ConfigStatusResponse } from '@/api/admin'

function buildSetting(overrides: Partial<AdminSetting> = {}): AdminSetting {
  return {
    id: 's1',
    key: 'APP_NAME',
    value: 'Subtracker',
    value_type: 'string',
    is_secret: false,
    description: 'Application name',
    category: 'application',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const healthyStatus: ConfigStatusResponse = {
  total_expected: 5,
  total_found: 5,
  valid_count: 5,
  incomplete_count: 0,
  missing_count: 0,
  extra_count: 0,
  missing: [],
  incomplete: [],
  valid: [],
  extra: [],
  is_healthy: true,
  recommendations: [],
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mockConfig(opts: any = {}) {
  const { settings = [], status = healthyStatus, listStatus = 200 } = opts
  server.use(
    // Register /status before the bare /config list handler.
    http.get('*/admin/config/status', () => HttpResponse.json(status)),
    http.get('*/admin/config', () =>
      listStatus === 200
        ? HttpResponse.json({
            items: settings,
            total: settings.length,
            page: 1,
            page_size: 100,
            total_pages: 1,
          })
        : HttpResponse.json({ detail: 'boom' }, { status: listStatus }),
    ),
  )
}

function row(text: string) {
  return within(screen.getByText(text).closest('tr') as HTMLElement)
}

afterEach(() => {
  vi.restoreAllMocks()
})

// NOTE: the create/edit setting flow is intentionally not covered. That modal
// contains a Chakra Switch ("Is Secret?"); opening a Switch-containing focus-
// trapped modal triggers a Chakra/jsdom commit-phase error ("Cannot set
// property focus"), the same environment limitation seen with AdminUsersPage.
// The delete flow (window.confirm, no modal) covers a mutation path here.

describe('AdminConfigPage', () => {
  it('shows a loading spinner while settings are being fetched', () => {
    server.use(
      http.get('*/admin/config/status', () => HttpResponse.json(healthyStatus)),
      http.get('*/admin/config', async () => {
        await delay('infinite')
        return HttpResponse.json({
          items: [],
          total: 0,
          page: 1,
          page_size: 100,
          total_pages: 1,
        })
      }),
    )

    renderWithProviders(<AdminConfigPage />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders settings and the healthy configuration status', async () => {
    mockConfig({ settings: [buildSetting()] })

    renderWithProviders(<AdminConfigPage />)

    expect(
      await screen.findByRole('heading', { name: 'System Configuration' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('All configuration settings are properly configured ✓'),
    ).toBeInTheDocument()
    expect(screen.getByText('APP_NAME')).toBeInTheDocument()
    expect(screen.getByText('Subtracker')).toBeInTheDocument()
  })

  it('surfaces configuration issues when the status is unhealthy', async () => {
    mockConfig({
      settings: [buildSetting()],
      status: {
        ...healthyStatus,
        valid_count: 4,
        missing_count: 1,
        is_healthy: false,
        missing: [
          {
            key: 'JWT_SECRET',
            category: 'system',
            required: true,
            description: 'JWT signing secret',
          },
        ],
        recommendations: ['Set JWT_SECRET'],
      },
    })

    renderWithProviders(<AdminConfigPage />)

    expect(
      await screen.findByText('Configuration Issues Detected'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('❌ Missing Required Settings (1)'),
    ).toBeInTheDocument()
    expect(screen.getByText('JWT_SECRET')).toBeInTheDocument()
  })

  it('shows an error toast when settings fail to load', async () => {
    mockConfig({ listStatus: 500 })

    renderWithProviders(<AdminConfigPage />)

    expect(await screen.findByText('Error loading settings')).toBeInTheDocument()
  })

  it('shows the empty state when there are no settings', async () => {
    mockConfig({ settings: [] })

    renderWithProviders(<AdminConfigPage />)

    expect(await screen.findByText('No settings found')).toBeInTheDocument()
  })

  it('deletes a setting after confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    let deletedKey: string | null = null
    mockConfig({ settings: [buildSetting()] })
    server.use(
      http.delete('*/admin/config/APP_NAME', () => {
        deletedKey = 'APP_NAME'
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()

    renderWithProviders(<AdminConfigPage />)
    await screen.findByText('APP_NAME')

    await user.click(row('APP_NAME').getByRole('button', { name: 'Delete' }))

    expect(confirmSpy).toHaveBeenCalled()
    expect(await screen.findByText('Setting deleted')).toBeInTheDocument()
    expect(deletedKey).toBe('APP_NAME')
  })

  it('reveals a secret value when visibility is toggled', async () => {
    mockConfig({
      settings: [
        buildSetting({
          key: 'OPENAI_API_KEY',
          value: 'sk-secret',
          is_secret: true,
          value_type: 'string',
          category: 'ai',
        }),
      ],
    })
    const user = userEvent.setup()

    renderWithProviders(<AdminConfigPage />)
    await screen.findByText('OPENAI_API_KEY')

    // The value is masked until toggled.
    expect(screen.getByText('••••••••')).toBeInTheDocument()
    await user.click(
      row('OPENAI_API_KEY').getByRole('button', { name: 'Toggle visibility' }),
    )

    expect(screen.getByText('sk-secret')).toBeInTheDocument()
  })
})
