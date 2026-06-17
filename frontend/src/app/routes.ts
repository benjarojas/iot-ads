import { createBrowserRouter } from 'react-router';
import { Dashboard } from './pages/Dashboard';
import { Configuration } from './pages/Configuration';
import { Replay } from './pages/Replay';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Dashboard,
  },
  {
    path: '/config',
    Component: Configuration,
  },
  {
    path: '/replay',
    Component: Replay,
  },
], {
  // Honour the Vite base path so routing works under a sub-path (e.g. /IoT-ADS).
  basename: import.meta.env.BASE_URL.replace(/\/$/, '') || '/',
});
