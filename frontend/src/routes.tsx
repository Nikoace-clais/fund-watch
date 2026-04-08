import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { FundDetail } from './pages/FundDetail'
import { Portfolio } from './pages/Portfolio'
import { Market } from './pages/Market'
import { Dca } from './pages/Dca'
import { ImportPage } from './pages/ImportPage'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    children: [
      { index: true, Component: Dashboard },
      { path: 'funds/:code', Component: FundDetail },
      { path: 'portfolio', Component: Portfolio },
      { path: 'market', Component: Market },
      { path: 'dca', Component: Dca },
      { path: 'import', Component: ImportPage },
    ],
  },
])
