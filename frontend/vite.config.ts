import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// import { VitePWA } from 'vite-plugin-pwa'  // Temporarily disabled
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Core vendor chunks
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'chakra-vendor': ['@chakra-ui/react', '@emotion/react', '@emotion/styled', 'framer-motion'],
          'query-vendor': ['@tanstack/react-query'],
          // Feature chunks
          'charts': ['recharts'],
          // Admin features
          'admin': [
            './src/pages/admin/ConfigPage',
            './src/components/admin/AdminAnnouncementsPage',
            './src/components/admin/AdminUsersPage',
            './src/components/admin/AdminLogsPage',
            './src/components/admin/AdminSecurityEventsPage',
            './src/components/admin/AdminIPWhitelistPage',
            './src/components/admin/AdminFeedbackMetricsPage',
          ],
        },
      },
    },
    // Optimize chunk sizes
    chunkSizeWarningLimit: 500,
    sourcemap: false, // Disable sourcemaps in production for smaller builds
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // Remove console logs in production
        drop_debugger: true,
      },
    },
  },
  plugins: [
    react(),
    // PWA plugin temporarily disabled due to container setup issues
    // VitePWA({
    //   registerType: 'autoUpdate',
    //   includeAssets: ['icon-192.svg', 'icon-512.svg'],
    //   manifest: {
    //     name: 'Subscription Tracker',
    //     short_name: 'SubTracker',
    //     description: 'Track and manage your subscriptions with automated email detection',
    //     theme_color: '#3182ce',
    //     background_color: '#ffffff',
    //     display: 'standalone',
    //     orientation: 'portrait',
    //     start_url: '/',
    //     icons: [
    //       {
    //         src: '/icon-192.svg',
    //         sizes: '192x192',
    //         type: 'image/svg+xml',
    //         purpose: 'any maskable',
    //       },
    //       {
    //         src: '/icon-512.svg',
    //         sizes: '512x512',
    //         type: 'image/svg+xml',
    //         purpose: 'any maskable',
    //       },
    //     ],
    //   },
    //   workbox: {
    //     globPatterns: ['**/*.{js,css,html,svg,png,ico,txt,woff2}'],
    //     runtimeCaching: [
    //       {
    //         urlPattern: /^https:\/\/api\./,
    //         handler: 'NetworkFirst',
    //         options: {
    //           cacheName: 'api-cache',
    //           expiration: {
    //             maxEntries: 50,
    //             maxAgeSeconds: 5 * 60, // 5 minutes
    //           },
    //           networkTimeoutSeconds: 10,
    //         },
    //       },
    //       {
    //         urlPattern: /^https:\/\/.*\.(?:png|jpg|jpeg|svg|gif|webp)$/,
    //         handler: 'CacheFirst',
    //         options: {
    //           cacheName: 'image-cache',
    //           expiration: {
    //             maxEntries: 100,
    //             maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
    //           },
    //         },
    //       },
    //     ],
    //   },
    //   devOptions: {
    //     enabled: true,
    //     type: 'module',
    //   },
    // }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true,
    },
  },
})
