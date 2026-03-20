import { createBrowserRouter, Navigate, Link } from 'react-router-dom';
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
import { Settings } from './pages/Settings';
import { Orders } from './pages/Orders';
import { Activities } from './pages/Activities';
import { Calendar } from './pages/Calendar';
import { Assets } from './pages/Assets';
import { ScannerSymbol } from './pages/ScannerSymbol';
import { OrderDetail } from './pages/OrderDetail';

function NotFound() {
  return (
    <div className="page-stack">
      <h1 className="page-title">404 Not Found</h1>
      <p className="muted-text">The page you're looking for doesn't exist.</p>
      <Link to="/command">← Back to Command Center</Link>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    errorElement: <NotFound />,
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
      { path: 'history', element: <Navigate to="/shadow-trades" replace /> },
      { path: 'settings', element: <Settings /> },
      { path: 'orders', element: <Orders /> },
      { path: 'orders/:orderId', element: <OrderDetail /> },
      { path: 'activities', element: <Activities /> },
      { path: 'calendar', element: <Calendar /> },
      { path: 'assets', element: <Assets /> },
      { path: 'scanner/symbol/:symbol', element: <ScannerSymbol /> },
      { path: '*', element: <NotFound /> },
    ],
  },
]);
