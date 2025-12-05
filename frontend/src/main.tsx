import React from 'react'
import ReactDOM from 'react-dom/client'
import { ChakraProvider, ColorModeScript } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
// import { registerSW } from 'virtual:pwa-register'  // Temporarily disabled
import App from './App'
import theme from './theme'
import './i18n/config'  // Initialize i18next

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000, // 30 seconds
      refetchOnWindowFocus: false,
    },
  },
})

// PWA registration temporarily disabled
// const updateSW = registerSW({
//   onNeedRefresh() {
//     // Show a toast/notification to the user about the update
//     if (confirm('New content available. Reload to update?')) {
//       updateSW(true)
//     }
//   },
//   onOfflineReady() {
//     console.log('App ready to work offline')
//   },
//   immediate: true,
// })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ColorModeScript initialColorMode={theme.config.initialColorMode} />
    <ChakraProvider theme={theme}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </ChakraProvider>
  </React.StrictMode>,
)
