/**
 * App — root React component.
 * Renders the Dashboard layout wrapped in an ErrorBoundary so that
 * unexpected render errors show a user-friendly fallback instead of
 * a blank screen.
 *
 * Requirements: 4.4, 4.5
 */

import React from 'react';
import { Dashboard } from './components/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';

export function App(): React.ReactElement {
  return (
    <ErrorBoundary>
      <Dashboard />
    </ErrorBoundary>
  );
}

export default App;
