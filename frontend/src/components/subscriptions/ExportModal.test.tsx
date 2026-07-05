import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExportModal } from './ExportModal'
import { renderWithProviders } from '@/test/renderWithProviders'
import { exportApi } from '@/api/export'

// ExportModal delegates the actual export to exportApi, which performs browser
// I/O (URL.createObjectURL, anchor download, window.open) that jsdom does not
// implement. Spy on the API so we can assert the modal's behaviour in isolation.
afterEach(() => {
  vi.restoreAllMocks()
})

const DEFAULT_FILTERS = {
  startDate: '',
  endDate: '',
  activeOnly: false,
  category: '',
}

describe('ExportModal', () => {
  it('renders the export options', async () => {
    renderWithProviders(<ExportModal isOpen onClose={vi.fn()} />)

    expect(await screen.findByText('Export Subscriptions')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export PDF' })).toBeInTheDocument()
  })

  it('exports to CSV and closes on success', async () => {
    const onClose = vi.fn()
    const exportCSV = vi
      .spyOn(exportApi, 'exportCSV')
      .mockResolvedValue(new Blob(['id,provider']))
    const downloadCSV = vi
      .spyOn(exportApi, 'downloadCSV')
      .mockImplementation(() => {})
    const user = userEvent.setup()

    renderWithProviders(<ExportModal isOpen onClose={onClose} />)
    await screen.findByText('Export Subscriptions')

    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    expect(await screen.findByText('Export successful')).toBeInTheDocument()
    expect(exportCSV).toHaveBeenCalledWith(DEFAULT_FILTERS)
    expect(downloadCSV).toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })

  it('shows an error toast and stays open when the CSV export fails', async () => {
    const onClose = vi.fn()
    vi.spyOn(exportApi, 'exportCSV').mockRejectedValue(new Error('nope'))
    const user = userEvent.setup()

    renderWithProviders(<ExportModal isOpen onClose={onClose} />)
    await screen.findByText('Export Subscriptions')

    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    expect(await screen.findByText('Export failed')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('exports to PDF and closes on success', async () => {
    const onClose = vi.fn()
    const exportPDF = vi
      .spyOn(exportApi, 'exportPDF')
      .mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderWithProviders(<ExportModal isOpen onClose={onClose} />)
    await screen.findByText('Export Subscriptions')

    await user.click(screen.getByRole('button', { name: 'Export PDF' }))

    expect(await screen.findByText('Opening PDF report')).toBeInTheDocument()
    expect(exportPDF).toHaveBeenCalledWith(DEFAULT_FILTERS)
    expect(onClose).toHaveBeenCalled()
  })

  it('passes the selected filters to the export', async () => {
    const exportCSV = vi
      .spyOn(exportApi, 'exportCSV')
      .mockResolvedValue(new Blob())
    vi.spyOn(exportApi, 'downloadCSV').mockImplementation(() => {})
    const user = userEvent.setup()

    renderWithProviders(<ExportModal isOpen onClose={vi.fn()} />)
    await screen.findByText('Export Subscriptions')

    await user.selectOptions(screen.getByRole('combobox'), 'streaming')
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    expect(exportCSV).toHaveBeenCalledWith({
      startDate: '',
      endDate: '',
      activeOnly: true,
      category: 'streaming',
    })
  })

  it('clears the active filters', async () => {
    const user = userEvent.setup()

    renderWithProviders(<ExportModal isOpen onClose={vi.fn()} />)
    await screen.findByText('Export Subscriptions')

    await user.selectOptions(screen.getByRole('combobox'), 'gaming')
    const clearButton = await screen.findByRole('button', {
      name: 'Clear Filters',
    })
    await user.click(clearButton)

    expect(
      screen.queryByRole('button', { name: 'Clear Filters' }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('combobox')).toHaveValue('')
  })

  it('calls onClose when Cancel is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()

    renderWithProviders(<ExportModal isOpen onClose={onClose} />)
    await screen.findByText('Export Subscriptions')

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onClose).toHaveBeenCalled()
  })
})
