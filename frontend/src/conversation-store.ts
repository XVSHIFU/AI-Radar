import { reactive } from "vue";
export type Attachment={id:string;title:string};
export type ConversationMessage={id:string;role:"user"|"assistant";text:string;createdAt:number;scope:string;filters?:Record<string,unknown>;mode:"demo"|"live";citations?:{index:number;title:string;quote_text?:string;source_url:string;paragraph_id?:string}[];status?:string;attachment?:Attachment};
export type Conversation={id:string;title:string;draft:string;createdAt:number;updatedAt:number;messages:ConversationMessage[]};
const key="conversations";let memory:Conversation[]=[];let writes=Promise.resolve();export const storageState=reactive({failed:false});
function snapshot(rows:Conversation[]):Conversation[]{return JSON.parse(JSON.stringify(rows)) as Conversation[]}
function valid(value:unknown):value is Conversation[]{return Array.isArray(value)&&value.every(x=>x&&typeof x==="object"&&typeof (x as Conversation).id==="string"&&Array.isArray((x as Conversation).messages))}
function open():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{const request=indexedDB.open("ai-radar-conversations",1);request.onupgradeneeded=()=>request.result.createObjectStore(key);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)})}
export async function loadConversations(){try{const db=await open();const rows=await new Promise<unknown>((resolve,reject)=>{const tx=db.transaction(key);const request=tx.objectStore(key).get("all");request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});db.close();memory=valid(rows)?rows:[];return memory}catch{storageState.failed=true;return memory}}
export function saveConversations(rows:Conversation[]){memory=snapshot(rows);writes=writes.then(async()=>{try{const db=await open();await new Promise<void>((resolve,reject)=>{const tx=db.transaction(key,"readwrite");tx.objectStore(key).put(snapshot(memory),"all");tx.oncomplete=()=>resolve();tx.onerror=()=>{tx.abort();reject(tx.error)}});db.close()}catch{storageState.failed=true}});return writes}
export function exportConversation(value:Conversation){return JSON.stringify(snapshot([value])[0],null,2)}
