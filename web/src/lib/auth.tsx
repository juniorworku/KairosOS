import {createContext,useContext,useEffect,type ReactNode} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {api,ApiError,clearPrivateData,offlineUser,rememberUser,setAccount} from '../api/client';
import type {User} from '../api/types';
interface Auth {user:User|null;loading:boolean;error:unknown;refresh:()=>Promise<void>;logout:()=>Promise<void>}
const Context=createContext<Auth|null>(null);
export function AuthProvider({children}:{children:ReactNode}){const client=useQueryClient();const query=useQuery({queryKey:['me'],queryFn:async()=>{try{const user=await api<User>('/me');setAccount(user.id);await rememberUser(user);return user;}catch(error){if(error instanceof ApiError&&error.status===401){await clearPrivateData();return null;}if(!navigator.onLine){const user=await offlineUser();if(user){setAccount(user.id);return user;}}throw error;}},retry:false,staleTime:60000});useEffect(()=>{if(query.data)setAccount(query.data.id);},[query.data]);async function refresh(){await client.invalidateQueries({queryKey:['me']});}async function logout(){await api('/auth/logout','POST');await clearPrivateData();client.clear();window.location.assign('/welcome');}return <Context.Provider value={{user:query.data??null,loading:query.isLoading,error:query.error,refresh,logout}}>{children}</Context.Provider>}
export function useAuth(){const value=useContext(Context);if(!value)throw new Error('AuthProvider missing');return value;}
