import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';

export function Layout() {
  return (
    <div className="layout layout--with-sidebar">
      <Sidebar />
      <div className="layout__body">
        <TopBar />
        <main className="layout__main">
          <div className="page-content">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
