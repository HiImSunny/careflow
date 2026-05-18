/**
 * main.tsx — application entry point.
 * Mounts the React app to the #root DOM element.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import { App } from './App';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error(
    'Root element #root not found. Ensure index.html contains <div id="root"></div>.'
  );
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
