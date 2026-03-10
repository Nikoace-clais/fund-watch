import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { FundDetail } from './pages/FundDetail'
import { Portfolio } from './pages/Portfolio'
import { Market } from './pages/Market'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    children: [
      { index: true, Component: Dashboard },
      { path: 'funds/:code', Component: FundDetail },
      { path: 'portfolio', Component: Portfolio },
      { path: 'market', Component: Market },
    ],
  },
])
