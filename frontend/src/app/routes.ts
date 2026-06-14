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
]);
