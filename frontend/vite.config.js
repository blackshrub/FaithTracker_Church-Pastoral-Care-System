import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  // Use Babel-based React plugin with React Compiler
  plugins: [
    react({
      babel: {
        plugins: [
          ['babel-plugin-react-compiler', {
            // React Compiler configuration
            target: '19', // Target React 19
          }],
        ],
      },
    }),
    // PWA Plugin - only caches static assets, NOT API calls
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icon-192x192.svg', 'icon-512x512.svg'],
      manifest: {
        name: 'FaithTracker - Pastoral Care System',
        short_name: 'FaithTracker',
        description: 'Multi-tenant pastoral care management system for GKBJ church',
        theme_color: '#14b8a6',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: '/',
        orientation: 'portrait-primary',
        categories: ['productivity', 'lifestyle'],
        icons: [
          {
            src: '/icon-192x192.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
          },
          {
            src: '/icon-512x512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
          },
          {
            src: '/icon-512x512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        // Only cache static assets - NEVER cache API calls
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}'],
        // Explicitly exclude API routes from caching
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            // Cache static images
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
            },
          },
          {
            // Cache fonts
            urlPattern: /\.(?:woff|woff2|ttf|eot)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'fonts-cache',
              expiration: {
                maxEntries: 20,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
            },
          },
          // NO API caching - always network-first for data freshness
        ],
      },
    }),
  ],

  // Path alias to match existing @ imports
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  // Development server configuration
  server: {
    port: 3000,
    open: false,
    // Proxy API requests to backend during development
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },

  // Build configuration
  build: {
    outDir: 'build', // Match CRA output directory for compatibility
    sourcemap: false,
    // Use multiple CPU cores for faster builds
    minify: 'esbuild',
    // Optimize chunk splitting for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          // React core - smallest possible chunk
          'react-vendor': ['react', 'react-dom'],
          // Router separate for route-based code splitting
          'router-vendor': ['react-router-dom'],
          // UI libraries - only used components
          'ui-vendor': [
            '@radix-ui/react-alert-dialog',
            '@radix-ui/react-avatar',
            '@radix-ui/react-checkbox',
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-label',
            '@radix-ui/react-popover',
            '@radix-ui/react-progress',
            '@radix-ui/react-select',
            '@radix-ui/react-separator',
            '@radix-ui/react-slot',
            '@radix-ui/react-tabs',
            'lucide-react',
            'sonner',
          ],
          // Charts - lazy loaded, separate chunk
          'charts-vendor': ['chart.js', 'react-chartjs-2'],
          // Data fetching
          'query-vendor': ['@tanstack/react-query'],
          // Utilities
          'utils-vendor': ['axios', 'date-fns', 'clsx', 'tailwind-merge', 'zod'],
          // i18n
          'i18n-vendor': ['i18next', 'react-i18next'],
        },
      },
    },
    // Increase chunk size warning limit
    chunkSizeWarningLimit: 1000,
  },

  // CSS configuration
  css: {
    postcss: './postcss.config.js',
  },

  // Define environment variables that will be replaced at build time
  define: {
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'development'),
  },
});
