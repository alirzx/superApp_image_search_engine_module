export type Collection = {id:string; name:string};
export type Job = {job_id:string;image_id:string;status:string;error:string|null};
export type SearchResult = {image_id:string;score:number;rank:number;thumbnail_url:string;metadata:{filename:string;width:number;height:number}};
export type SearchResponse = {request_id:string;collection_id:string;query_type:string;processing_time_ms:number;results:SearchResult[]};
const BASE='/api';
async function readError(response:Response):Promise<string>{
  try {const body=await response.json();return typeof body.detail==='string'?body.detail:JSON.stringify(body.detail??body);}
  catch {return `HTTP ${response.status}`;}
}
export async function request<T>(path:string, init:RequestInit={}):Promise<T>{
  const headers=new Headers(init.headers);
  if(init.body && typeof init.body==='string') headers.set('Content-Type','application/json');
  const response=await fetch(`${BASE}${path}`,{...init,headers,cache:'no-store'});
  if(!response.ok)throw new Error(await readError(response));
  if(response.status===204) return undefined as T;
  return response.json() as Promise<T>;
}
export async function fetchThumbnail(path:string):Promise<Blob>{
  const response=await fetch(`${BASE}${path}`,{cache:'no-store'});
  if(!response.ok)throw new Error('Thumbnail access denied');
  return response.blob();
}
export async function textSearch(query:string,collection_id:string,top_k:number):Promise<SearchResponse>{
  return request('/v1/search/text',{method:'POST',body:JSON.stringify({query,collection_id,top_k})});
}
export async function imageSearch(file:File,collection_id:string,top_k:number):Promise<SearchResponse>{
  const body=new FormData();body.append('file',file);body.append('collection_id',collection_id);body.append('top_k',String(top_k));
  return request('/v1/search/image',{method:'POST',body});
}
export async function uploadImages(files:File[],collection_id:string):Promise<{accepted:{image_id:string;job_id:string}[];rejected:{error:string}[]}>{
  if(files.length===1){const body=new FormData();body.append('file',files[0]);body.append('collection_id',collection_id);
    const result=await request<{image_id:string;job_id:string}>('/v1/images',{method:'POST',body});return {accepted:[result],rejected:[]};}
  const body=new FormData();files.forEach(f=>body.append('files',f));body.append('collection_id',collection_id);
  return request('/v1/images/batch',{method:'POST',body});
}
