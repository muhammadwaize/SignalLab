export const API = (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) }, cache: 'no-store' });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try { const data = await res.json(); message = data.detail || data.error || message; } catch {}
    throw new Error(message);
  }
  return res.json();
}
export const money = (n: unknown) => new Intl.NumberFormat('en-PK', { style: 'currency', currency: 'PKR', maximumFractionDigits: 0 }).format(Number(n || 0));
export const number = (n: unknown) => new Intl.NumberFormat('en-US').format(Number(n || 0));
export const pretty = (s: string) => s.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
