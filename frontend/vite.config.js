// vite.config.js is the configuration file for Vite

// Import the React plugin for Vite
import react from '@vitejs/plugin-react'

// Import the function used to define Vite configuration
import { defineConfig } from 'vite'

// Configure Vite for this project
// https://vite.dev/config/
export default defineConfig({
  // Enable React support, including JSX processing and Fast Refresh
  plugins: [react()],
})
