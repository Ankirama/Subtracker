import { ReactElement, ReactNode } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { ChakraProvider } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'

export interface ProviderOptions {
  route?: string
  queryClient?: QueryClient
  withAuth?: boolean
}

export function renderWithProviders(
  ui: ReactElement,
  options: ProviderOptions & Omit<RenderOptions, 'wrapper'> = {},
) {
  const {
    route = '/',
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { staleTime: Infinity, retry: false },
        mutations: { retry: false },
      },
    }),
    withAuth = true,
    ...renderOptions
  } = options

  const Wrapper = ({ children }: { children: ReactNode }) => {
    const tree = (
      <ChakraProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>
    )
    return withAuth ? <AuthProvider>{tree}</AuthProvider> : tree
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions })
}
