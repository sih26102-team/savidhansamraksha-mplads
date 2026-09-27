import { createRoot } from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from '@/components/error-boundary';
import { setBaseUrl } from '@/lib/api';
import './index.css';

const apiUrl = import.meta.env.VITE_API_URL || (typeof window !== 'undefined' && window.location.hostname.includes('vercel.app') ? 'https://savidhan-api-server.onrender.com' : '');
if (apiUrl) {
  setBaseUrl(apiUrl.replace(/\/+$/, ''));
}
createRoot(document.getElementById('root'), {
    // Keeps caught errors off reportError(), which would raise the dev overlay.
    onCaughtError: (error, errorInfo) => {
        console.error(error, errorInfo.componentStack);
    },
}).render(<ErrorBoundary>
    <App />
  </ErrorBoundary>);
