'use client';
import { useMemo, useState } from 'react';
import { Search, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { pretty, number } from '@/lib/api';
import Link from 'next/link';
const longCols = ['comment_text','comment','description','reasons','title'];
function cellValue(key:string,value:unknown) {
  if(value===null || value===undefined || value==='') return <span className="muted">—</span>;
  if(typeof value==='boolean' || key==='strict' || key==='purchased' || key==='intent' || key==='show_off' || key==='influencer' || key==='saw_ad' || key==='word_of_mouth') return <span className={`pill ${value?'pill-green':'pill-muted'}`}>{value?'Yes':'No'}</span>;
  if(key==='sentiment' || key==='status' || key==='data_origin' || key==='verdict') return <span className={`pill ${String(value).toLowerCase().includes('positive')||value==='done'?'pill-green':String(value).toLowerCase().includes('negative')||value==='failed'?'pill-red':'pill-muted'}`}>{String(value)}</span>;
  if(typeof value==='number') return <span className="numeric">{Number.isInteger(value)?number(value):value.toFixed(3)}</span>;
  const str=String(value);
  return longCols.includes(key) ? <span className="cell-long" title={str}>{str}</span> : <span title={str}>{str.length>54?str.slice(0,51)+'…':str}</span>;
}
export function DataTable({columns,rows,total,page,pages,onPage,downloadUrl,onSearch}:{columns:string[],rows:Record<string,unknown>[],total:number,page:number,pages:number,onPage:(p:number,q?:string)=>void,downloadUrl?:string,onSearch?:(q:string)=>void}) {
 const [query,setQuery]=useState('');
 const filtered=useMemo(()=>onSearch||!query?rows:rows.filter(r=>Object.values(r).some(v=>String(v??'').toLowerCase().includes(query.toLowerCase()))),[rows,query,onSearch]);
 return <div className="table-shell"><div className="table-toolbar"><div className="table-search"><Search size={15}/><input value={query} onChange={e=>{setQuery(e.target.value);onSearch?.(e.target.value);}} placeholder={onSearch?"Search all records…":"Search visible rows…"}/></div><div className="table-tools"><span>{number(total)} records</span>{downloadUrl&&<a className="button button-quiet button-small" href={downloadUrl}><Download size={14}/> Export CSV</a>}</div></div><div className="table-scroll"><table className="data-grid"><thead><tr>{columns.map(c=><th key={c}>{pretty(c)}</th>)}</tr></thead><tbody>{filtered.length?filtered.map((row,i)=><tr key={String(row.id??row.comment_id??i)}>{columns.map(c=><td key={c} className={longCols.includes(c)?'wide-cell':''}>{cellValue(c,row[c])}</td>)}</tr>):<tr><td colSpan={columns.length} className="no-rows">No matching records found.</td></tr>}</tbody></table></div><div className="table-pagination"><span>Page <b>{page}</b> of <b>{pages}</b></span><div><button className="page-btn" disabled={page<=1} onClick={()=>onPage(page-1,query)}><ChevronLeft size={15}/> Previous</button><button className="page-btn" disabled={page>=pages} onClick={()=>onPage(page+1,query)}>Next <ChevronRight size={15}/></button></div></div></div>
}
