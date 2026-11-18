
'use client';

import { ReactNode, useEffect, useState } from 'react';
import { Sidebar } from './sidebar';
import { Bell } from 'lucide-react';
import { API } from '@/lib/api';

type ApiStatus = 'checking' | 'connected' | 'offline';

export function Shell({
  children,
  title,
  subtitle,
}: {
  children: ReactNode;
  title: string;
  subtitle?: string;
}) {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking');

  useEffect(() => {
    let active = true;

    const checkApi = async () => {
      try {
        const response = await fetch(`${API}/api/health`, {
          cache: 'no-store',
        });

        if (!response.ok) throw new Error('API unavailable');

        const data = await response.json();

        if (active) {
          setApiStatus(data.status === 'ok' ? 'connected' : 'offline');
        }
      } catch {
        if (active) setApiStatus('offline');
      }
    };

    checkApi();

    const interval = setInterval(checkApi, 10000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const statusText = {
    checking: 'Checking API...',
    connected: 'API connected',
    offline: 'API offline',
  };

  return (
    <div className="app-shell">
      <Sidebar />

      <main className="main">
        <header className="topbar">
          <div className="crumb">
            WORKSPACE <span>/</span> {title.toUpperCase()}
          </div>

          <div className="top-actions">
            <div className={`api-status api-${apiStatus}`}>
              <i />
              {statusText[apiStatus]}
            </div>

            <button className="icon-button" aria-label="Notifications">
              <Bell size={17} />
            </button>

            <div className="avatar">BI</div>
          </div>
        </header>

        <div className="page-wrap">
          <div className="page-heading">
            <div>
              <h1>{title}</h1>
              {subtitle && <p>{subtitle}</p>}
            </div>
          </div>

          {children}
        </div>

        <footer className="footer">
          SignalLab <span>·</span> Brand intelligence workspace
        </footer>
      </main>
    </div>
  );
}
