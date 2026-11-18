'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, BarChart3, BrainCircuit, Database, LayoutDashboard, Megaphone, PanelLeftClose } from 'lucide-react';
const links = [
  { href: '/', label: 'Overview', icon: LayoutDashboard },
  { href: '/sentiment', label: 'Sentiment analysis', icon: Activity },
  { href: '/optimizer', label: 'Ad optimizer', icon: Megaphone },
  { href: '/project3', label: 'Audience insights', icon: BrainCircuit },
  { href: '/tables', label: 'Data tables', icon: Database },
];
export function Sidebar() {
  const path = usePathname();
  return <aside className="sidebar"><Link href="/" className="brand"><span className="brand-mark"><BarChart3 size={19}/></span><span>Signal<span className="brand-light">Lab</span><small>BRAND INTELLIGENCE</small></span></Link><div className="nav-label">WORKSPACE</div><nav>{links.map(({href,label,icon:Icon}) => <Link key={href} href={href} className={`nav-link ${(path===href || (href!=='/' && path.startsWith(href)))?'active':''}`}><Icon size={17}/><span>{label}</span></Link>)}</nav><div className="sidebar-bottom"><div className="connection-dot"/> <span>Local workspace</span><span className="version">v1.0</span></div></aside>;
}
