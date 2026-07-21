import React from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import { router } from './routes'
import { queryClient } from './lib/queries'
import { ColorProvider } from './lib/color-context'
import { ProviderConfigProvider } from './lib/provider-config'
import { PortfolioProvider } from './lib/portfolio-context'
import './styles/index.css'

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ColorProvider>
        <ProviderConfigProvider>
          <PortfolioProvider>
            <RouterProvider router={router} />
          </PortfolioProvider>
        </ProviderConfigProvider>
      </ColorProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
