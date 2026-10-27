import {useState,type ReactNode,type FormEvent} from 'react';
import {copy as c} from '../../copy/en';
export function Field({label,children,hint}:{label:string;children:ReactNode;hint?:string}){return <label className="field"><span>{label}</span>{children}{hint&&<small>{hint}</small>}</label>}
export function Notice({error}:{error:unknown}){return error?<p role="alert" className="error-note">{error instanceof Error?error.message:c.requestFailed}</p>:null;}
export function Empty({title,children}:{title:string;children?:ReactNode}){return <div className="empty-state"><p>{title}</p>{children}</div>}
export function SubmitForm({onSubmit,children,className=''}:{onSubmit:()=>Promise<void>;children:(busy:boolean)=>ReactNode;className?:string}){const[error,setError]=useState<unknown>();const[busy,setBusy]=useState(false);async function submit(event:FormEvent){event.preventDefault();setError(undefined);setBusy(true);try{await onSubmit();}catch(error){setError(error);}finally{setBusy(false);}}return <form className={className} onSubmit={e=>void submit(e)}><Notice error={error}/>{children(busy)}</form>}
