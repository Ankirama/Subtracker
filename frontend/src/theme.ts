import { extendTheme, type ThemeConfig } from '@chakra-ui/react'

// Color mode configuration
const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
}

const theme = extendTheme({
  config,
  semanticTokens: {
    colors: {
      // Subtle text color - adapts to color mode
      'text.subtle': {
        default: 'gray.600',
        _dark: 'gray.400',
      },
      // Muted text color - even more subtle
      'text.muted': {
        default: 'gray.500',
        _dark: 'gray.500',
      },
      // Background colors
      'bg.surface': {
        default: 'white',
        _dark: 'gray.800',
      },
      'bg.subtle': {
        default: 'gray.50',
        _dark: 'gray.800',
      },
      'bg.muted': {
        default: 'gray.100',
        _dark: 'gray.700',
      },
      // Accent backgrounds (for info cards, highlights)
      'bg.accent.blue': {
        default: 'blue.50',
        _dark: 'blue.900',
      },
      'bg.accent.orange': {
        default: 'orange.50',
        _dark: 'gray.700',
      },
      'bg.accent.green': {
        default: 'green.50',
        _dark: 'green.900',
      },
      'bg.accent.red': {
        default: 'red.50',
        _dark: 'red.900',
      },
      'bg.accent.yellow': {
        default: 'yellow.50',
        _dark: 'yellow.900',
      },
      // Border colors
      'border.subtle': {
        default: 'gray.200',
        _dark: 'gray.700',
      },
    },
  },
  breakpoints: {
    base: '0px',      // Mobile (0-767px)
    md: '768px',      // Tablet (768-1023px)
    lg: '1024px',     // Desktop (1024px+)
  },
  styles: {
    global: (props: { colorMode: string }) => ({
      // Prevent zoom on iOS when focusing inputs
      'input, textarea, select': {
        fontSize: '16px',
      },
      // Safe area support for notched devices and color mode
      body: {
        paddingBottom: 'env(safe-area-inset-bottom)',
        bg: props.colorMode === 'dark' ? 'gray.900' : 'white',
        color: props.colorMode === 'dark' ? 'whiteAlpha.900' : 'gray.800',
      },
    }),
  },
  components: {
    Container: {
      baseStyle: {
        maxW: {
          base: '100%',
          lg: 'container.xl',
        },
        px: {
          base: 4,     // 16px padding on mobile
          md: 6,       // 24px padding on tablet
          lg: 8,       // 32px padding on desktop
        },
      },
    },
    Button: {
      baseStyle: {
        // Ensure minimum touch target size (44px)
        minH: '44px',
        minW: '44px',
      },
    },
    IconButton: {
      baseStyle: {
        // Ensure minimum touch target size
        minW: '44px',
        minH: '44px',
      },
    },
  },
})

export default theme
