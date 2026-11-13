import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source = (await readFile(new URL('../src/lib/api.js', import.meta.url), 'utf8')).replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
globalThis.localStorage={getItem:()=>null};
let deadline; let received;
const original=AbortSignal.timeout;
AbortSignal.timeout=(ms)=>{deadline=ms;return new AbortController().signal;};
globalThis.fetch=async(_url,options)=>{received=options.signal;return {ok:true,json:async()=>({})};};
const {api}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
for(const path of ['/auth/login','/auth/register']){await api(path);assert.equal(deadline,75000);}
await api('/market/history');assert.equal(deadline,20000);
const controller=new AbortController();await api('/auth/me',{signal:controller.signal});assert.equal(received,controller.signal);
AbortSignal.timeout=original;
console.log('PASS auth cold-start budget75s; market budget20s; explicit startup cancellation preserved');
