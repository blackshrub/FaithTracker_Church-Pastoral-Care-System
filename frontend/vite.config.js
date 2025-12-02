import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  // SWC is 20-70x faster than Babel for JSX transformation
  plugins: [react()],

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
    // Optimize chunk splitting
    rollupOptions: {
      output: {
        manualChunks: {
          // React core
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          // UI libraries
          'ui-vendor': [
            '@radix-ui/react-alert-dialog',
            '@radix-ui/react-avatar',
            '@radix-ui/react-checkbox',
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-label',
            '@radix-ui/react-popover',
            '@radix-ui/react-select',
            '@radix-ui/react-separator',
            '@radix-ui/react-slot',
            '@radix-ui/react-switch',
            '@radix-ui/react-tabs',
            '@radix-ui/react-toast',
            '@radix-ui/react-toggle',
            '@radix-ui/react-tooltip',
            'lucide-react',
            'sonner',
          ],
          // Charts
          'charts-vendor': ['chart.js', 'react-chartjs-2'],
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
  // Note: We keep PostCSS for Tailwind processing, but use LightningCSS for minification
  css: {
    postcss: './postcss.config.js',
  },

  // Define environment variables that will be replaced at build time
  define: {
    // This ensures process.env.NODE_ENV works
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'development'),
  },
});
