/**
 * Centralised API base URL helper.
 *
 * - In development (Vite dev server): uses `/api` — proxied to localhost:8000
 *   via vite.config.ts.
 * - In production (Vercel): uses the `VITE_API_URL` env variable which should
 *   be set to the Render backend URL, e.g. `https://careflow-api.onrender.com`
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_URL
    ? (import.meta.env.VITE_API_URL as string).replace(/\/$/, '')
    : '';

/**
 * Build a full API URL.
 * Usage: apiUrl('/api/orchestrate') → 'https://careflow-api.onrender.com/api/orchestrate'
 *        apiUrl('/api/orchestrate') → '/api/orchestrate'  (dev)
 */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

/**
 * Build a WebSocket URL, converting http(s) → ws(s).
 * Usage: wsUrl('/api/speech/transcribe')
 */
export function wsUrl(path: string): string {
  if (API_BASE_URL) {
    const wsBase = API_BASE_URL.replace(/^https/, 'wss').replace(/^http/, 'ws');
    return `${wsBase}${path}`;
  }
  // Fallback: derive from current page origin (dev)
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
}
