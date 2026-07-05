import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { PullToRefresh } from './PullToRefresh'
import { renderWithProviders } from '@/test/renderWithProviders'

describe('PullToRefresh', () => {
  it('renders its children', () => {
    renderWithProviders(
      <PullToRefresh onRefresh={vi.fn().mockResolvedValue(undefined)}>
        <div>Pull content</div>
      </PullToRefresh>,
      { withAuth: false },
    )

    expect(screen.getByText('Pull content')).toBeInTheDocument()
  })
})
