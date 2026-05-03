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

  // i18next is initialized globally as a side-effect of importing
  // '@/i18n/config' from setup.ts (mirroring main.tsx), so useTranslation
  // works without an I18nextProvider wrapper here.
  // AuthProvider must be inside MemoryRouter because it calls useNavigate().
  const Wrapper = ({ children }: { children: ReactNode }) => {
    const inner = withAuth ? <AuthProvider>{children}</AuthProvider> : children
    return (
      <ChakraProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>{inner}</MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>
    )
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions })
}
