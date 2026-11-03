import React from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import HomePage from './pages/HomePage'
import { registerServiceWorker } from './pwa/registerServiceWorker'

registerServiceWorker()

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HomePage />
  </React.StrictMode>,
)
