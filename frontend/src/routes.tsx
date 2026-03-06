import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { FundExplorer } from './pages/FundExplorer'
import { FundDetail } from './pages/FundDetail'
import { Portfolio } from './pages/Portfolio'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    children: [
      { index: true, Component: Dashboard },
      { path: 'funds', Component: FundExplorer },
      { path: 'funds/:code', Component: FundDetail },
      { path: 'portfolio', Component: Portfolio },
      {
        path: 'market',
        element: (
          <div className="flex flex-col items-center justify-center h-[60vh] text-center">
            <h2 className="text-2xl font-bold text-slate-800">行情数据</h2>
            <p className="text-slate-500 mt-2">功能开发中，敬请期待</p>
          </div>
        ),
      },
    ],
  },
])
