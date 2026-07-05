import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { MarkdownRenderer } from './MarkdownRenderer'
import { renderWithProviders } from '@/test/renderWithProviders'

describe('MarkdownRenderer', () => {
  it('renders bold markdown as a <strong> element', () => {
    renderWithProviders(<MarkdownRenderer content="This is **bold** text" />, {
      withAuth: false,
    })

    const strong = screen.getByText('bold')
    expect(strong.tagName).toBe('STRONG')
  })

  it('renders links with an href', () => {
    renderWithProviders(
      <MarkdownRenderer content="[Google](https://google.com)" />,
      { withAuth: false },
    )

    const link = screen.getByRole('link', { name: 'Google' })
    expect(link).toHaveAttribute('href', 'https://google.com')
  })

  it('sanitizes embedded scripts', () => {
    const { container } = renderWithProviders(
      <MarkdownRenderer content={'Safe text<script>alert(1)</script>'} />,
      { withAuth: false },
    )

    expect(screen.getByText(/Safe text/)).toBeInTheDocument()
    expect(container.querySelector('script')).toBeNull()
  })
})
