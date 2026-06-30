// Builds a same-origin WebSocket URL so the connection is proxied by whatever
// serves the app (the Vite dev proxy locally, or nginx in the container).
// `path` should start with "/", e.g. "/api/ws/convert".
export function apiWebSocketUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}
