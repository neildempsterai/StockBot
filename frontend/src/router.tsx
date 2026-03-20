import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { CommandCenter } from './pages/CommandCenter';
import { LiveSignalFeed } from './pages/LiveSignalFeed';
import { SignalDetail } from './pages/SignalDetail';
import { IntelligenceCenter } from './pages/IntelligenceCenter';
import { AiReferee } from './pages/AiReferee';
import { Performance } from './pages/Performance';
import { Experiments } from './pages/Experiments';
import { Portfolio } from './pages/Portfolio';
import { ShadowTrades } from './pages/ShadowTrades';
import { SystemHealth } from './pages/SystemHealth';
import { StrategyLab } from './pages/StrategyLab';
import { History } from './pages/History';
import { Settings } from './pages/Settings';
import { Orders } from './pages/Orders';
import { Activities } from './pages/Activities';
import { Calendar } from './pages/Calendar';
import { Assets } from './pages/Assets';
import { ScannerSymbol } from './pages/ScannerSymbol';
import { OrderDetail } from './pages/OrderDetail';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/command" replace /> },
      { path: 'overview', element: <CommandCenter /> },
      { path: 'command', element: <CommandCenter /> },
      { path: 'signals', element: <LiveSignalFeed /> },
      { path: 'signals/:signalUuid', element: <SignalDetail /> },
      { path: 'intelligence', element: <IntelligenceCenter /> },
      { path: 'ai-referee', element: <AiReferee /> },
      { path: 'performance', element: <Performance /> },
      { path: 'experiments', element: <Experiments /> },
      { path: 'portfolio', element: <Portfolio /> },
      { path: 'shadow-trades', element: <ShadowTrades /> },
      { path: 'system-health', element: <SystemHealth /> },
      { path: 'strategy-lab', element: <StrategyLab /> },
      { path: 'history', element: <History /> },
      { path: 'settings', element: <Settings /> },
      { path: 'orders', element: <Orders /> },
      { path: 'orders/:orderId', element: <OrderDetail /> },
      { path: 'activities', element: <Activities /> },
      { path: 'calendar', element: <Calendar /> },
      { path: 'assets', element: <Assets /> },
      { path: 'scanner/symbol/:symbol', element: <ScannerSymbol /> },
    ],
  },
]);
