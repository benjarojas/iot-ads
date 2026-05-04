import { useEffect } from 'react';
import { RouterProvider } from 'react-router';
import { router } from './routes';
import { dashboardWs } from './services/websocket';

export default function App() {
  useEffect(() => {
    dashboardWs.connect();
    return () => dashboardWs.disconnect();
  }, []);

  return <RouterProvider router={router} />;
}
