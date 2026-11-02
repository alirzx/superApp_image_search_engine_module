import React, {useCallback, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Collection, SearchResult, fetchThumbnail, getKey, imageSearch, request, setKey, textSearch, uploadImages} from './api';
import './style.css';

type Mode = 'text'|'image';
function SecureImage({path,alt}:{path:string;alt:string}){
  const [src,setSrc]=useState('');
  useEffect(()=>{let cancelled=false;let url='';fetchThumbnail(path).then(b=>{if(!cancelled){url=URL.createObjectURL(b);setSrc(url);}}).catch(()=>setSrc(''));
    return ()=>{cancelled=true;if(url)URL.revokeObjectURL(url);};},[path]);
  return src?<img src={src} alt={alt} loading="lazy"/>:<div className="image-placeholder">◻</div>;
}
function ResultCard({result, onDelete}:{result:SearchResult; onDelete:(id:string)=>void}){
  return <article className="result"><div className="result-photo"><SecureImage path={result.thumbnail_url} alt={result.metadata.filename}/><span className="rank">#{result.rank}</span></div>
    <div className="result-body"><strong title={result.metadata.filename}>{result.metadata.filename}</strong>
    <div className="card-meta"><span>{result.metadata.width} × {result.metadata.height}</span><span>امتیاز شباهت: {result.score.toFixed(3)}</span></div>
    <button className="text-button" onClick={()=>onDelete(result.image_id)}>حذف از مجموعه</button></div></article>;
}
function App(){
  const [keyInput,setKeyInput]=useState(getKey());
  const [connected,setConnected]=useState(false);
  const [collections,setCollections]=useState<Collection[]>([]);
  const [collection,setCollection]=useState('default');
  const [collectionName,setCollectionName]=useState('');
  const [mode,setMode]=useState<Mode>('text');
  const [text,setText]=useState('');
  const [queryImage,setQueryImage]=useState<File|null>(null);
  const [uploadFiles,setUploadFiles]=useState<File[]>([]);
  const [results,setResults]=useState<SearchResult[]>([]);
  const [queryInfo,setQueryInfo]=useState('');
  const [busy,setBusy]=useState(false);
  const [uploadBusy,setUploadBusy]=useState(false);
  const [pendingJobs,setPendingJobs]=useState<string[]>([]);
  const [status,setStatus]=useState('');
  const [error,setError]=useState('');
  const [drag,setDrag]=useState(false);

  const refresh=useCallback(async()=>{
    const data=await request<{collections:Collection[]}>('/v1/collections');setCollections(data.collections);setConnected(true);
  },[]);
  useEffect(()=>{if(getKey())refresh().catch(()=>setConnected(false));},[refresh]);
  useEffect(()=>{if(pendingJobs.length===0)return;const timer=setInterval(async()=>{
    try{const states=await Promise.all(pendingJobs.map(id=>request<{status:string;error:string|null}>(`/v1/jobs/${id}`)));
      const active=pendingJobs.filter((_,i)=>states[i].status==='processing'||states[i].status==='queued');
      setPendingJobs(active);
      if(active.length===0)setStatus(`ایندکس‌گذاری تمام شد. ${states.filter(s=>s.status==='completed').length} پردازش موفق در آخرین بررسی.`);
    }catch(e){setError((e as Error).message);}
  },1800);return ()=>clearInterval(timer);},[pendingJobs]);
  async function connect(){setKey(keyInput.trim());setError('');try{await refresh();setStatus('ارتباط با API برقرار شد.');}catch(e){setConnected(false);setError((e as Error).message);}}
  async function addCollection(){if(!collectionName.trim())return;try{const c=await request<Collection>('/v1/collections',{method:'POST',body:JSON.stringify({name:collectionName.trim()})});await refresh();setCollection(c.id);setCollectionName('');}catch(e){setError((e as Error).message);}}
  async function upload(){if(!uploadFiles.length)return;setUploadBusy(true);setError('');try{const d=await uploadImages(uploadFiles,collection);
    setPendingJobs(prev=>[...prev,...d.accepted.map(x=>x.job_id)]);setStatus(`${d.accepted.length} تصویر در صف ایندکس‌گذاری قرار گرفت. ${d.rejected.length} مورد رد شد.`);setUploadFiles([]);}
    catch(e){setError((e as Error).message);}finally{setUploadBusy(false);}}
  async function search(){if(mode==='text'&&!text.trim()||mode==='image'&&!queryImage)return;setBusy(true);setError('');
    try{const r=mode==='text'?await textSearch(text.trim(),collection,12):await imageSearch(queryImage!,collection,12);
      setResults(r.results);setQueryInfo(`${r.results.length} نتیجه · ${r.processing_time_ms.toFixed(0)} میلی‌ثانیه`);}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function deleteImage(id:string){if(!window.confirm('این تصویر از مجموعه حذف شود؟'))return;try{await request<void>(`/v1/images/${id}`,{method:'DELETE'});setResults(r=>r.filter(x=>x.image_id!==id));}
    catch(e){setError((e as Error).message);}}
  const canSearch=mode==='text'?Boolean(text.trim()):Boolean(queryImage);
  return <div className="app" dir="rtl">
    <header className="topbar"><div className="brand"><div className="brand-logo">✳</div><div><b>SuperApp</b><small>AI SERVICES / MODULE 04</small></div></div>
      <span className="service-badge"><i className={connected?'online':'offline'}/>{connected?'متصل به API':'بدون اتصال'}</span></header>
    <main><section className="hero"><div className="eyebrow">VISION INTELLIGENCE · CPU FIRST</div><h1>جست‌وجوی هوشمند <span>تصاویر</span></h1>
      <p>در مجموعه‌ تصاویر خود جست‌وجو کنید؛ با یک عکس مشابه یا توضیح متنی فارسی و انگلیسی.</p><div className="hero-pills"><span>Image → Image</span><span>Text → Image</span><span>SigLIP2 · CPU</span></div></section>
      <section className="api-config panel"><div className="panel-label"><span className="step">01</span><div><h2>اتصال به سرویس</h2><p>کلید دسترسی فقط برای این نشست مرورگر نگهداری می‌شود.</p></div></div>
        <div className="inline"><input type="password" aria-label="API Key" placeholder="X-API-Key" value={keyInput} onChange={e=>setKeyInput(e.target.value)} /><button onClick={connect}>بررسی اتصال</button></div></section>
      <div className="columns"><section className="panel"><div className="panel-label"><span className="step">02</span><div><h2>مجموعه تصاویر</h2><p>یک مجموعه انتخاب کرده یا مجموعه جدید بسازید.</p></div></div>
        <label>مجموعه فعال</label><select value={collection} onChange={e=>{setCollection(e.target.value);setResults([]);}}>{collections.length?collections.map(c=><option key={c.id} value={c.id}>{c.name}</option>):<option value="default">Default</option>}</select>
        <div className="inline"><input value={collectionName} placeholder="نام مجموعه جدید" onChange={e=>setCollectionName(e.target.value)}/><button className="secondary" onClick={addCollection} disabled={!connected}>ساخت</button></div>
        <div className={`dropzone ${drag?'drag':''}`} onDragOver={e=>{e.preventDefault();setDrag(true);}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);setUploadFiles([...e.dataTransfer.files].filter(f=>f.type.startsWith('image/')));}}>
          <div className="upload-icon">↑</div><strong>تصاویر خود را اضافه کنید</strong><span>فایل‌ها را بکشید و رها کنید یا انتخاب کنید</span>
          <label className="file-button">انتخاب فایل‌ها<input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={e=>setUploadFiles([...e.target.files||[]])}/></label>
          {uploadFiles.length>0&&<div className="chosen">{uploadFiles.length} فایل انتخاب شده</div>}</div>
        <button className="full" onClick={upload} disabled={!connected||!uploadFiles.length||uploadBusy}>{uploadBusy?'در حال ارسال…':'آپلود و ایندکس تصاویر'}</button>
        {pendingJobs.length>0&&<p className="job-status">⏳ {pendingJobs.length} تصویر در انتظار پردازش</p>}</section>
      <section className="panel"><div className="panel-label"><span className="step">03</span><div><h2>جست‌وجو در تصاویر</h2><p>یکی از دو روش جست‌وجوی هوشمند را انتخاب کنید.</p></div></div>
        <div className="tabs"><button className={mode==='text'?'active':''} onClick={()=>setMode('text')}>⌕ جست‌وجو با متن</button><button className={mode==='image'?'active':''} onClick={()=>setMode('image')}>▧ جست‌وجو با تصویر</button></div>
        {mode==='text'?<><label htmlFor="query">توضیح تصویر</label><textarea id="query" value={text} onChange={e=>setText(e.target.value)} placeholder="مثلاً: یک گربه سفید روی مبل، یا یک خودروی قرمز در خیابان…"/>
          <p className="hint">از زبان فارسی یا انگلیسی استفاده کنید.</p><div className="examples"><span>پیشنهاد:</span>{['طبیعت و کوهستان','خودروی سفید','a cat on a sofa'].map(q=><button key={q} onClick={()=>setText(q)}>{q}</button>)}</div></>
        :<div className="image-query"><div className="upload-icon">▧</div><p>یک عکس برای جست‌وجوی تصاویر مشابه انتخاب کنید.</p><label className="file-button">انتخاب عکس<input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>setQueryImage(e.target.files?.[0]??null)}/></label>{queryImage&&<div className="chosen">{queryImage.name}</div>}</div>}
        <button className="full primary" onClick={search} disabled={!connected||!canSearch||busy}>{busy?'در حال جست‌وجو…':'جست‌وجوی تصاویر ←'}</button>
        <p className="footnote">رتبه‌بندی بر پایه شباهت برداری انجام می‌شود؛ امتیازها احتمال قطعی نیستند.</p></section></div>
      {error&&<div className="notice error" role="alert">{error}</div>}{status&&<div className="notice">{status}</div>}
      <section className="results-section"><div className="results-heading"><div><div className="eyebrow">RETRIEVAL RESULTS</div><h2>نتایج جست‌وجو</h2></div><span>{queryInfo||'هنوز جست‌وجویی انجام نشده است'}</span></div>
        {results.length?<div className="grid">{results.map(r=><ResultCard key={r.image_id} result={r} onDelete={deleteImage}/>)}</div>
        :<div className="empty"><div>▦</div><h3>تصاویر اینجا نمایش داده می‌شوند</h3><p>ابتدا چند تصویر ایندکس کنید، سپس با تصویر یا متن در آن‌ها جست‌وجو کنید.</p></div>}</section></main>
    <footer>SuperApp · Image Search Engine <span>FastAPI / React / FAISS / SQLite</span></footer></div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
