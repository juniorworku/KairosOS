import { request, config, PairingRequired, type FocusState } from './api';
import { makeRules, remaining } from './rules';
const EMPTY: FocusState={active_session:null,blocklist:[],ends_at:null};
let inFlight:Promise<void>|null=null;
async function install(state:FocusState):Promise<void>{
 const seconds=remaining(state.ends_at);const paused=state.pause_until&&Date.parse(state.pause_until)>Date.now();
 const existing=await chrome.declarativeNetRequest.getDynamicRules();
 const server=new URL((await config()).apiBase).hostname;const domains=seconds&&!paused?state.blocklist.filter(domain=>server!==domain&&!server.endsWith('.'+domain)):[];
 const redirect=domains.length>0&&await chrome.permissions.contains({origins:domains.flatMap(d=>['https://*.'+d+'/*','http://*.'+d+'/*'])});
 await chrome.declarativeNetRequest.updateDynamicRules({removeRuleIds:existing.filter(r=>r.id>=1000&&r.id<1100).map(r=>r.id),addRules:makeRules(domains,redirect)});
 await chrome.storage.local.set({focusState:state});
 if(seconds)await chrome.alarms.create('session-end',{when:Date.parse(state.ends_at!)});else await chrome.alarms.clear('session-end');
 if(paused)await chrome.alarms.create('pause-end',{when:Date.parse(state.pause_until!)});
 await chrome.action.setBadgeText({text:seconds?String(Math.ceil(seconds/60)):''});
 await chrome.action.setBadgeBackgroundColor({color:'#315c43'});
}
async function reconcile():Promise<void>{
 if(inFlight)return inFlight;
 inFlight=(async()=>{try{await install(await request<FocusState>('/state'));}catch(error){if(error instanceof PairingRequired){await install(EMPTY);return;}const stored=await chrome.storage.local.get('focusState');const state=stored.focusState as FocusState|undefined;if(state&&remaining(state.ends_at))await install(state);else await install(EMPTY);}})().finally(()=>{inFlight=null;});
 return inFlight;
}
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='session-end')void install(EMPTY);else void reconcile();});
chrome.runtime.onStartup.addListener(()=>void reconcile());
chrome.runtime.onInstalled.addListener(()=>{void chrome.alarms.create('sync',{periodInMinutes:.5});void reconcile();});
chrome.runtime.onMessageExternal.addListener((_message,sender,respond)=>{if(!sender.url||!['http://localhost:5173','http://127.0.0.1:5173'].includes(new URL(sender.url).origin)){respond({ok:false});return false;}void reconcile().then(()=>respond({ok:true}));return true;});
chrome.runtime.onMessage.addListener((_message,_sender,respond)=>{void reconcile().then(()=>respond({ok:true}));return true;});
void reconcile();
