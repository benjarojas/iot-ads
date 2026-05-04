import { createBrowserRouter } from 'react-router';
import { Dashboard } from './pages/Dashboard';
import { Configuration } from './pages/Configuration';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Dashboard,
  },
  {
    path: '/config',
    Component: Configuration,
  },
]);
