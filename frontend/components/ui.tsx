import { ReactNode } from 'react';
export function Metric({label,value,detail,icon}:{label:string,value:ReactNode,detail?:string,icon?:ReactNode}) { return <div className="metric-card"><div className="metric-top"><span>{label}</span><span className="metric-icon">{icon}</span></div><div className="metric-value">{value}</div>{detail&&<div className="metric-detail">{detail}</div>}</div> }
export function Section({title,detail,action,children}:{title:string,detail?:string,action?:ReactNode,children:ReactNode}) {return <section className="panel"><div className="panel-head"><div><h2>{title}</h2>{detail&&<p>{detail}</p>}</div>{action}</div>{children}</section>}
export function Empty({title,detail}:{title:string,detail:string}) {return <div className="empty-state"><div className="empty-symbol">◎</div><h3>{title}</h3><p>{detail}</p></div>}
export function ErrorNote({message}:{message:string}) {return <div className="error-note">{message}</div>}
