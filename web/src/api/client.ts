import {openDB} from 'idb';
import type {User} from './types';
export class ApiError extends Error { constructor(public status:number, public code:string, message:string) {super(message);} }
const db=()=>openDB('kairos-offline',1,{upgrade(database){database.createObjectStore('reads');database.createObjectStore('queue',{keyPath:'id'});}});
let accountId='';
let csrf='';
export function setAccount(id:string){accountId=id;}
export async function rememberUser(user:User){accountId=user.id;await(await db()).put('reads',user,'profile');}
export async function offlineUser():Promise<User|undefined>{return(await db()).get('reads','profile');}
export async function clearPrivateData(){accountId='';csrf='';const database=await db();await Promise.all([database.clear('reads'),database.clear('queue')]);}
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
 const key=`${accountId}:${path}`;const cacheable=method==='GET'&&accountId&&/^\/(goals|plan\/week|focus\/(stats|active|sessions)|trajectory|reflection|busy|seasons)/.test(path);
 if(!navigator.onLine&&cacheable){const cached=await(await db()).get('reads',key) as T|undefined;if(cached!==undefined)return cached;}
 if(method!=='GET'&&!csrf){const response=await fetch('/api/v1/auth/csrf',{credentials:'include'});if(!response.ok)throw new ApiError(response.status,'csrf','Sign in again to continue.');const data=await response.json() as {csrf_token:string};csrf=data.csrf_token;}
 let response:Response;
 try{response=await fetch(`/api/v1${path}`,{method,credentials:'include',headers:{'Content-Type':'application/json',...(method!=='GET'?{'X-CSRF-Token':csrf}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});}catch(error){if(cacheable){const cached=await(await db()).get('reads',key) as T|undefined;if(cached!==undefined)return cached;}throw error;}
 if(!response.ok){const data=await response.json().catch(()=>({})) as {error?:{code?:string;message?:string};detail?:string|{msg:string}[]};let message=data.error?.message;if(!message)message=typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(d=>d.msg).join('. '):`Request failed (${response.status}).`;throw new ApiError(response.status,data.error?.code||'request_failed',message);}
 if(response.status===204)return undefined as T;
 const result=await response.json() as T;if(path==='/auth/magic/verify')csrf='';if(cacheable)await(await db()).put('reads',result,key);return result;
}
interface Queued {id:string;account:string;path:string;body:unknown}
export async function queueWrite(path:string,body:Record<string,unknown>){const id=crypto.randomUUID();await(await db()).put('queue',{id,account:accountId,path,body:{...body,client_event_id:id}} satisfies Queued);}
export async function replayQueue(){if(!navigator.onLine||!accountId)return;const database=await db();const queued=await database.getAll('queue') as Queued[];for(const item of queued){if(item.account!==accountId)continue;try{await api(item.path,'POST',item.body);await database.delete('queue',item.id);}catch(error){if(error instanceof ApiError&&error.status<500&&error.status!==401&&error.status!==403){throw error;}break;}}}
export async function readDraft<T>(key:string):Promise<T|undefined>{return(await db()).get('reads',`${accountId}:draft:${key}`);}
export async function saveDraft(key:string,value:unknown){await(await db()).put('reads',value,`${accountId}:draft:${key}`);}
export async function deleteDraft(key:string){await(await db()).delete('reads',`${accountId}:draft:${key}`);}
export async function streamRequest(path:string,body:unknown,signal?:AbortSignal){if(!csrf){const data=await api<{csrf_token:string}>('/auth/csrf');csrf=data.csrf_token;}const response=await fetch(`/api/v1${path}`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body),signal});if(!response.ok){const data=await response.json() as {error?:{message?:string};detail?:{message?:string}|string};throw new Error(data.error?.message||(typeof data.detail==='string'?data.detail:data.detail?.message)||'Could not get a reply.');}return response;}
