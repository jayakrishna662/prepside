// eslint.config.js is a configuration file that tells ESLint,
// what rules it should follow when checking your code. ESLint is like a code checker.
// npm run lint --> It checks your code and reports problems according to this configuration.
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),  // Ignore the generated dist folder, bcz we need to check problems in source files only
  {
    files: ['**/*.{js,jsx}'], // apply these rules to JavaScript and JSX files throughout the project.
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
])
