/**
 * ErrorBoundary — catches unexpected React render errors and displays a
 * user-friendly fallback UI instead of a blank screen.
 *
 * Requirements: 4.4, 4.5
 */

import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Optional custom fallback. If omitted, the default error UI is shown. */
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Class-based error boundary that wraps its children and catches any
 * unhandled errors thrown during rendering, lifecycle methods, or
 * constructors of the child component tree.
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // Log to console for developer visibility; in production this could
    // be forwarded to an error-tracking service.
    console.error('[ErrorBoundary] Uncaught error:', error, info.componentStack);
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          className="flex min-h-screen flex-col items-center justify-center gap-6 bg-slate-100 px-4 text-center"
          role="alert"
          aria-label="Application error"
        >
          <AlertCircle
            className="h-12 w-12 text-red-500"
            aria-hidden="true"
          />
          <div>
            <h1 className="mb-2 text-xl font-bold text-slate-800">
              Something went wrong
            </h1>
            <p className="max-w-md text-sm text-slate-600">
              An unexpected error occurred in the application. You can try
              reloading the page or clicking the button below to recover.
            </p>
            {this.state.error && (
              <p className="mt-2 max-w-md rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {this.state.error.message}
              </p>
            )}
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={this.handleReset}
              className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors"
              aria-label="Try to recover from error"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition-colors"
              aria-label="Reload the page"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
