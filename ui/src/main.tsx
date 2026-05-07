import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { initializeConfig } from './lib/environment'

// Initialize configuration and render app
async function initializeApp() {
  try {
    // Load runtime configuration from the server
    await initializeConfig();

    // Render the React app after configuration is loaded
    createRoot(document.getElementById('root')!).render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  } catch (error) {
    console.error('Failed to initialize application:', error);

    // Render app anyway with default configuration
    createRoot(document.getElementById('root')!).render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  }
}

// Start the application
initializeApp();
