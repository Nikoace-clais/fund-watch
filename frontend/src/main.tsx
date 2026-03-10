import React from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { router } from './routes'
import { ColorProvider } from './lib/color-context'
import './styles/index.css'

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ColorProvider>
      <RouterProvider router={router} />
    </ColorProvider>
  </React.StrictMode>,
)