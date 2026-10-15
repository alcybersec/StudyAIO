import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { i18nReady } from './i18n'
import { App } from './App'
import { initMonitoring } from './lib/monitoring'

// No-op unless VITE_SENTRY_DSN is set at build time.
void initMonitoring()

// Wait for the stored language's bundle so a Russian user never sees a flash
// of English; resolves immediately for English, which is bundled.
void i18nReady.finally(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
