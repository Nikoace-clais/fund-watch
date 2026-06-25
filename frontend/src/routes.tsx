import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { PageState } from './components/PageState'

// Catches route errors, including lazy chunk load failures after a redeploy
function RouteError() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-slate-500">
      <p className="text-sm">页面加载失败，可能是应用已更新，请刷新重试</p>
      <button
        onClick={() => window.location.reload()}
        className="px-4 py-2 text-sm rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 transition-colors"
      >
        刷新页面
      </button>
    </div>
  )
}

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    HydrateFallback: () => <PageState loading />,
    ErrorBoundary: RouteError,
    children: [
      {
        index: true,
        lazy: async () => ({ Component: (await import('./pages/Dashboard')).Dashboard }),
      },
      {
        path: 'funds/:code',
        lazy: async () => ({ Component: (await import('./pages/FundDetail')).FundDetail }),
      },
      {
        path: 'portfolio',
        lazy: async () => ({ Component: (await import('./pages/Portfolio')).Portfolio }),
      },
      {
        path: 'market',
        lazy: async () => ({ Component: (await import('./pages/Market')).Market }),
      },
      {
        path: 'ai-select',
        lazy: async () => ({ Component: (await import('./pages/AiSelect')).AiSelect }),
      },
      {
        path: 'import',
        lazy: async () => ({ Component: (await import('./pages/ImportPage')).ImportPage }),
      },
    ],
  },
])
