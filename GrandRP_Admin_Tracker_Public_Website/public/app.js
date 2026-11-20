(()=>{'use strict';
const $=id=>document.getElementById(id);
const RANGE_IDS=['preset','dateFrom','dateTo'];
const TZ='Europe/London';
const resolvedPattern=/\b(approved|rejected|reviewed|accepted|denied|closed|resolved|finished|completed|declined)\b/i;
const state={results:[],source:'',active:false,controller:null,period:null,summary:null,selectedAdmin:null,visible:60,scanned:0,pages:0,errors:0,missingDates:0,complete:false,status:'idle',lastAt:null};
const num=v=>Number(v).toLocaleString();
const fmtDate=ms=>new Intl.DateTimeFormat('en-AU',{timeZone:TZ,dateStyle:'medium',timeStyle:'short'}).format(new Date(ms));
function localParts(ms){const parts=new Intl.DateTimeFormat('en-US',{timeZone:TZ,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(ms));return Object.fromEntries(parts.filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));}
function dayKey(ms){const p=localParts(ms);return `${p.year}-${p.month}-${p.day}`;}
const utcDay=s=>new Date(`${s}T00:00:00.000Z`);
const isoDay=d=>d.toISOString().slice(0,10);
function shiftDay(s,n){const d=utcDay(s);d.setUTCDate(d.getUTCDate()+n);return isoDay(d);}
function rangeFor(preset,start,end){const today=dayKey(Date.now());let from=today,to=today;const weekday=(utcDay(today).getUTCDay()+6)%7;
 switch(preset){case 'today':break;case 'yesterday':from=to=shiftDay(today,-1);break;case 'week':from=shiftDay(today,-weekday);break;case 'previous-week':from=shiftDay(today,-weekday-7);to=shiftDay(from,6);break;case 'last7':from=shiftDay(today,-6);break;case 'month':from=today.slice(0,8)+'01';break;case 'previous-month':to=shiftDay(today.slice(0,8)+'01',-1);from=to.slice(0,8)+'01';break;case 'last30':from=shiftDay(today,-29);break;case 'custom':from=start;to=end;break;default:throw Error('Unsupported date range.');}
 if(!/^\d{4}-\d{2}-\d{2}$/.test(from)||!/^\d{4}-\d{2}-\d{2}$/.test(to)||isoDay(utcDay(from))!==from||isoDay(utcDay(to))!==to)throw Error('Choose both valid custom dates.');
 if(from>to)throw Error('Start date must be before or equal to end date.');
 if(from>today)throw Error('Start date cannot be in the future.');
 const days=(utcDay(to)-utcDay(from))/86400000;if(days>366)throw Error('Choose a range of 367 days or less.');
 return {from,to,label:`${from} to ${to}`,timezone:TZ};}
function selectedRange(){return rangeFor($('preset').value,$('dateFrom').value,$('dateTo').value);}
function setNotice(text='',isError=false){$('notice').textContent=text;$('notice').classList.toggle('hidden',!text);$('notice').classList.toggle('error',isError);}
function setStatus(text,badge='Not scanned'){ $('status').textContent=text;$('statusType').textContent=badge;}
function loading(on){state.active=on;$('scanBtn').disabled=on;$('stopBtn').classList.toggle('hidden',!on);RANGE_IDS.forEach(id=>$(id).disabled=on);$('csvFile').disabled=on;}
function progress(){const val=state.active?Math.min(99,(state.pages/50)*100):state.results.length||state.pages?100:0;$('progressBar').style.width=`${val}%`;}
function currentRows(){if(state.source==='csv'){const period=selectedRange();return state.results.filter(r=>{const day=dayKey(r.date);return day>=period.from&&day<=period.to;});}return state.results;}
function grouped(rows){const map=new Map();for(const row of rows){const id=row.adminId||`name:${row.name.toLowerCase()}`;if(!map.has(id))map.set(id,{id,name:row.name,count:0});map.get(id).count++;}return [...map.values()].sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name));}
function filterRows(){let rows=currentRows();if($('resolvedOnly').checked)rows=rows.filter(r=>resolvedPattern.test(r.status));const search=$('adminFilter').value.trim().toLowerCase();if(search)rows=rows.filter(r=>r.name.toLowerCase().includes(search));if(state.selectedAdmin)rows=rows.filter(r=>r.adminId===state.selectedAdmin);return rows;}
function element(tag,className,text,parent){const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=text;if(parent)parent.append(el);return el;}
function cell(tr,txt,css=''){return element('td',css,txt,tr);}
function render(){let base;try{base=currentRows();}catch{return;}
 const resolved=$('resolvedOnly').checked;const effective=resolved?base.filter(r=>resolvedPattern.test(r.status)):base;
 const filtered=filterRows(),groups=grouped(filtered),overview=grouped(effective);
 $('statScanned').textContent=state.source?num(state.source==='csv'?base.length:state.scanned):'—';
 $('statCount').textContent=state.source?num(effective.length):'—';
 $('statAdmins').textContent=state.source?num(overview.length):'—';
 $('statPages').textContent=state.source?state.source==='csv'?'—':num(state.pages):'—';
 $('scanCoverage').textContent=state.source==='csv'?'Imported rows only':state.active?'Reading forum…':state.status==='complete'?'Range covered':state.status==='partial'?'Partial coverage':'Awaiting scan';
 $('resultWindow').textContent=state.source?`${state.source==='csv'?'Imported data':'Forum scan'} · ${state.period?.label||selectedRange().label} · ${state.status==='complete'?'complete':state.source==='csv'?'imported':state.active?'scanning':'partial'} · ${groups.length} admin(s)`:'Run a scan to view admin totals.';
 $('exportBtn').disabled=!filtered.length;
 const body=$('leaders');body.replaceChildren();if(!groups.length){const tr=element('tr','',undefined,body);const td=cell(tr,state.active?'Checking forum posts…':state.source?'No matching admins for this filter.':'No results yet. Start a scan or import a CSV.','empty-cell');td.colSpan=5;}
 else{const max=groups[0].count;groups.forEach((g,i)=>{const tr=element('tr','',undefined,body);cell(tr,String(i+1),'rank');const name=element('td','',undefined,tr);element('span','admin-crest',g.name.slice(0,1).toUpperCase(),name);element('span','admin-name',g.name,name);cell(tr,num(g.count),'right count-badge');const share=element('td','right share-cell',undefined,tr);element('span','share-text',`${(g.count/Math.max(1,filtered.length)*100).toFixed(1)}%`,share);const bar=element('div','share-bar',undefined,share);element('div','share-fill',undefined,bar).style.width=`${100*g.count/max}%`;const act=element('td','right',undefined,tr);const button=element('button','details-btn',state.selectedAdmin===g.id?'Selected ×':'View threads',act);button.type='button';button.addEventListener('click',()=>{state.selectedAdmin=state.selectedAdmin===g.id?null:g.id;state.visible=60;render();});});}
 renderChart(filtered);renderThreads(filtered);
}
function weekKey(ms){const k=dayKey(ms),d=utcDay(k),w=(d.getUTCDay()+6)%7;return 'Week '+shiftDay(k,-w);}
function chartKey(ms,group){return group==='month'?dayKey(ms).slice(0,7):group==='week'?weekKey(ms):dayKey(ms);}
function renderChart(rows){const chart=$('chart');chart.replaceChildren();chart.classList.toggle('empty-state',!rows.length);if(!rows.length){chart.textContent='No activity in the current filter.';return;}
 const counts=new Map();for(const row of rows){const k=chartKey(row.date,$('groupBy').value);counts.set(k,(counts.get(k)||0)+1);}
 const list=[...counts.entries()].sort((a,b)=>a[0].localeCompare(b[0]));const max=Math.max(...list.map(x=>x[1]));for(const [label,n] of list){const row=element('div','chart-row',undefined,chart);element('span','date',label,row);const track=element('div','track',undefined,row);element('div','fill',undefined,track).style.width=`${100*n/max}%`;element('strong','',String(n),row);}}
function safeThreadUrl(input){try{const url=new URL(input);return url.protocol==='https:'&&url.hostname==='gta5grand.com'&&url.pathname.startsWith('/forum/threads/')?url.href:null;}catch{return null;}}
function renderThreads(rows){const holder=$('threads');holder.replaceChildren();holder.classList.toggle('empty-state',!rows.length);const selected=state.selectedAdmin?rows[0]?.name:null;$('threadTitle').textContent=selected?`Threads: ${selected}`:'Matching threads';$('threadSubtitle').textContent=`${num(rows.length)} threads · ${state.selectedAdmin?'Selected admin':'Current filters'}`;$('clearAdmin').classList.toggle('hidden',!state.selectedAdmin);
 if(!rows.length){holder.textContent='No matching threads for this selection.';return;}
 for(const row of [...rows].sort((a,b)=>b.date-a.date).slice(0,state.visible)){const item=element('div','thread-item',undefined,holder);const link=element('a','',row.title||`Forum thread #${row.id}`,item);const url=safeThreadUrl(row.url);if(url){link.href=url;link.target='_blank';link.rel='noopener noreferrer';}else{link.removeAttribute('href');}
 const meta=element('div','thread-meta',undefined,item);element('span','',row.name,meta);element('span','','·',meta);element('span','',fmtDate(row.date),meta);element('span','','·',meta);element('span','thread-status',row.status||'Unlabelled',meta);}
 if(rows.length>state.visible){const more=element('button','load-more',`Show more (${num(rows.length-state.visible)} remaining)`,holder);more.addEventListener('click',()=>{state.visible+=60;renderThreads(rows);});}}
function csvCell(raw){const txt=String(raw??'');return `"${(/^[\s]*[=+\-@]/.test(txt)?"'"+txt:txt).replaceAll('"','""')}"`;}
function exportCsv(){const rows=filterRows().sort((a,b)=>b.date-a.date);if(!rows.length)return;const header=['Forum thread ID','Thread title','Admin name','Last reply date (Europe/London)','Last reply timestamp (UTC)','Status','Thread URL'];const records=rows.map(r=>[r.id,r.title,r.name,fmtDate(r.date),new Date(r.date).toISOString(),r.status,r.url]);const csv='\ufeff'+[header,...records].map(r=>r.map(csvCell).join(',')).join('\r\n');const u=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download=`grandrp-admin-report-${dayKey(Date.now())}.csv`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),3000);}
function saveState(){try{localStorage.setItem('grandrp-report-v2-london',JSON.stringify({results:state.results,source:state.source,period:state.period,scanned:state.scanned,pages:state.pages,errors:state.errors,missingDates:state.missingDates,complete:state.complete,status:state.status,lastAt:state.lastAt}));}catch{/* private mode/storage quota */}}
function restore(){try{const saved=JSON.parse(localStorage.getItem('grandrp-report-v2-london')||'null');if(!saved||!Array.isArray(saved.results))return;Object.assign(state,{...saved,active:false,controller:null,selectedAdmin:null,visible:60});const time=state.lastAt?fmtDate(state.lastAt):'earlier';setStatus(`Saved ${state.source==='csv'?'import':'scan'} from ${time}`,state.source==='csv'?'Imported':state.complete?'Saved':'Partial');if(state.source==='csv')state.period=selectedRange();else if(state.period?.from){$('preset').value='custom';$('customDates').classList.remove('hidden');$('dateFrom').value=state.period.from;$('dateTo').value=state.period.to;}progress();render();}catch{/* malformed cache */}}
function onDatesChanged(){const custom=$('preset').value==='custom';$('customDates').classList.toggle('hidden',!custom);if(state.source==='csv'){try{state.period=selectedRange();setNotice('This report includes imported rows only; the source CSV may not cover every thread in the selected period.');}catch{}render();return;}
 if(state.source&& !state.active){state.results=[];state.source='';state.period=null;state.pages=0;state.scanned=0;state.selectedAdmin=null;state.status='idle';state.complete=false;setStatus('Date range changed. Start a new scan.');setNotice('The previous scan used a different date window. Run a new scan to get accurate counts.');$('progressBar').style.width='0';render();}}
async function runScan(){if(state.active)return;let period;try{period=selectedRange();}catch(err){setNotice(err.message,true);return;}
 state.results=[];state.source='server';state.period=period;state.scanned=0;state.pages=0;state.errors=0;state.missingDates=0;state.complete=false;state.status='scanning';state.selectedAdmin=null;state.visible=60;const controller=new AbortController();state.controller=controller;
 loading(true);setNotice('');setStatus('Connecting to Grand RP…','Scanning');progress();render();
 try{const response=await fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preset:$('preset').value,start:$('dateFrom').value,end:$('dateTo').value}),signal:controller.signal});if(!response.ok){let message=`Website server returned ${response.status}.`;try{message=(await response.json()).detail||message;}catch{}throw Error(message);}if(!response.body)throw Error('The server did not provide a scan stream.');
 const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='',finished=false;
 while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines){if(!line.trim())continue;let update;try{update=JSON.parse(line);}catch{continue;}state.results=update.results||state.results;state.pages=update.pages??state.pages;state.scanned=update.scanned??state.scanned;state.errors=update.errors??state.errors;state.missingDates=update.missing_dates??state.missingDates;state.period=update.period||state.period;state.complete=!!update.complete;state.status=update.status||state.status;setStatus(update.phase||'Scanning…',update.type==='done'?(update.status==='complete'?'Complete':'Partial'):'Scanning');progress();render();
 if(update.type==='done'){finished=true;state.lastAt=Date.now();let message=update.message||'Scan finished.';if(update.status==='partial')message+='\nResults may be incomplete. '+state.errors+' post(s) could not be verified and '+state.missingDates+' thread(s) had unreadable dates.';setNotice(message,update.status==='partial');saveState();}}}
 if(!finished){state.status='partial';setNotice('The scan stream ended early. Displayed counts are partial.',true);} }
 catch(error){state.status='partial';if(controller.signal.aborted){setStatus('Scan stopped','Partial');setNotice('Stopped. Any numbers shown are incomplete.');}else{setStatus('Scan could not finish','Partial');const networkIssue=error instanceof TypeError && /fetch|network|load failed/i.test(error.message||'');setNotice(networkIssue?'Connection to the website scanner failed. The server may have stopped, restarted or timed out. Open /api/health on this site and check the server logs. Hosting publicly does not bypass Grand RP forum access restrictions.':(error.message||'Unknown scan error.'),true);}}
 finally{state.lastAt=Date.now();loading(false);progress();render();if(state.source)saveState();}}
function parseCsv(csv){const out=[];let row=[],field='',quoted=false;for(let i=0;i<csv.length;i++){const c=csv[i];if(quoted){if(c==='"'&&csv[i+1]==='"'){field+='"';i++;}else if(c==='"'){quoted=false;}else{field+=c;}}else if(c==='"'){quoted=true;}else if(c===','){row.push(field);field='';}else if(c==='\r'||c==='\n'){if(c==='\r'&&csv[i+1]==='\n')i++;row.push(field);if(row.some(v=>v!==''))out.push(row);row=[];field='';}else{field+=c;}}if(quoted)throw Error('CSV contains an unclosed quotation mark.');row.push(field);if(row.some(v=>v!==''))out.push(row);return out;}
// Convert a wall-clock date from an explicitly named time zone to a UTC timestamp.
// GMT/BST offsets are derived for the specific date, never hard-coded as UTC+0.
function wallClockMs(year,month,day,hour,minute,second,zone){
 if(zone==='browser')return new Date(year,month-1,day,hour,minute,second).getTime();
 if(zone==='Australia/Perth')return Date.UTC(year,month-1,day,hour,minute,second)-8*3600000;
 const utc=Date.UTC(year,month-1,day,hour,minute,second);
 const offsetAt=ms=>{const parts=new Intl.DateTimeFormat('en-GB',{timeZone:TZ,timeZoneName:'shortOffset'}).formatToParts(ms);const label=parts.find(p=>p.type==='timeZoneName')?.value||'GMT';const m=label.match(/^GMT([+-])(\d{1,2})(?::(\d{2}))?$/);return m?(m[1]==='-'?-1:1)*(Number(m[2])*60+Number(m[3]||0)):0;};
 let instant=utc-offsetAt(utc)*60000;
 instant=utc-offsetAt(instant)*60000;
 return instant;
}
function parseImportedDate(value,zone='browser'){
 const txt=String(value||'').trim().replace(/\s+at\s+/i,', ');
 if(/^\d{13}$/.test(txt))return Number(txt);
 if(/^\d{4}-\d{2}-\d{2}T/.test(txt)){const result=Date.parse(txt);if(Number.isFinite(result))return result;}
 let match=txt.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:[,\s]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?)?$/i);
 if(match){let hour=Number(match[4]||0);if(match[7])hour=(hour%12)+(match[7].toLowerCase()==='pm'?12:0);return wallClockMs(Number(match[3]),Number(match[2]),Number(match[1]),hour,Number(match[5]||0),Number(match[6]||0),zone);}
 match=txt.match(/^(\d{4})-(\d{2})-(\d{2})[ ,]+(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
 if(match)return wallClockMs(Number(match[1]),Number(match[2]),Number(match[3]),Number(match[4]),Number(match[5]),Number(match[6]||0),zone);
 // English medium-date CSVs exported by Intl.DateTimeFormat (e.g. 21 Nov 2026, 1:30 pm).
 match=txt.match(/^(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4}),?\s+(\d{1,2}):(\d{2})(?:\s*(am|pm))?$/i);
 if(match){const months='jan feb mar apr may jun jul aug sep oct nov dec'.split(' ');const month=months.indexOf(match[2].slice(0,3).toLowerCase())+1;if(month){let hour=Number(match[4]);if(match[6])hour=(hour%12)+(match[6].toLowerCase()==='pm'?12:0);return wallClockMs(Number(match[3]),month,Number(match[1]),hour,Number(match[5]),0,zone);}}
 // Legacy extension CSVs show browser-local dates without a timezone identifier.
 const result=Date.parse(txt);return Number.isFinite(result)?result:NaN;
}
function importCsv(text){const matrix=parseCsv(text.replace(/^\ufeff/,''));if(matrix.length<2)throw Error('No thread rows found in this CSV file.');const heads=matrix[0].map(h=>h.trim().toLowerCase());const col=(...names)=>{for(const n of names){const i=heads.indexOf(n);if(i>=0)return i;}return -1;};
 const iId=col('forum thread id','thread id'),iTitle=col('thread title','title'),iName=col('admin name','admin'),iDate=col('last reply date (europe/london)','last reply local date','last reply date (australia/perth)','date'),iIso=col('last reply timestamp (utc)'),iStatus=col('status'),iUrl=col('thread url','url');if([iTitle,iName,iUrl].some(i=>i<0)||(iDate<0&&iIso<0))throw Error('CSV must include Thread title, Admin name, a Last reply date or UTC timestamp, and Thread URL columns.');const csvZone=heads.includes('last reply date (europe/london)')?TZ:heads.includes('last reply date (australia/perth)')?'Australia/Perth':'browser';
 const seen=new Set(),results=[];let skipped=0;for(const cells of matrix.slice(1)){const name=(cells[iName]||'').trim(),url=safeThreadUrl((cells[iUrl]||'').trim()),dateMs=parseImportedDate((iIso>=0?cells[iIso]||cells[iDate]:cells[iDate])||'',csvZone);if(!name||!url||!Number.isFinite(dateMs)){skipped++;continue;}const id=(iId>=0?cells[iId]:'')||new URL(url).pathname.match(/\.(\d+)\/?$/)?.[1]||url;const threadKey=String(id);if(seen.has(threadKey))continue;seen.add(threadKey);results.push({id:threadKey,title:(cells[iTitle]||'').trim(),name,adminId:`name:${name.toLocaleLowerCase()}`,date:dateMs,url,status:iStatus>=0?(cells[iStatus]||'Unlabelled'):'Unlabelled'});}
 if(!results.length)throw Error('No valid dated Grand RP thread records were found in this CSV.');return {results,skipped};}
async function openCsv(file){if(!file)return;if(state.active){setNotice('Stop the current scan before importing a CSV.',true);return;}if(file.size>8_000_000){setNotice('The CSV exceeds the 8 MB limit.',true);return;}try{const {results,skipped}=importCsv(await file.text());state.results=results;state.source='csv';state.period=selectedRange();state.scanned=results.length;state.pages=0;state.complete=false;state.status='imported';state.selectedAdmin=null;state.visible=60;state.lastAt=Date.now();setStatus(`Imported ${num(results.length)} distinct threads`,'Imported');setNotice(`Showing imported records only. The original CSV may not cover every thread or date. ${skipped?`${skipped} invalid row(s) skipped.`:''}`);progress();render();saveState();}catch(error){setNotice(error.message,true);}finally{$('csvFile').value='';}}
$('preset').addEventListener('change',onDatesChanged);$('dateFrom').addEventListener('change',onDatesChanged);$('dateTo').addEventListener('change',onDatesChanged);$('scanBtn').addEventListener('click',runScan);$('stopBtn').addEventListener('click',()=>state.controller?.abort());$('adminFilter').addEventListener('input',()=>{state.selectedAdmin=null;state.visible=60;render();});$('resolvedOnly').addEventListener('change',()=>{state.visible=60;render();});$('groupBy').addEventListener('change',render);$('clearAdmin').addEventListener('click',()=>{state.selectedAdmin=null;render();});$('exportBtn').addEventListener('click',exportCsv);$('csvFile').addEventListener('change',e=>openCsv(e.target.files?.[0]));
restore();render();
})();
