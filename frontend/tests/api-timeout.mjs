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
let calls=0;
globalThis.fetch=async()=>{calls++;throw new DOMException('fixture deadline','TimeoutError');};
await assert.rejects(api('/auth/login'),/no automatic retry was sent/);assert.equal(calls,1);
await assert.rejects(api('/auth/register'),/may have reached the server.*Try signing in/);assert.equal(calls,2);
globalThis.fetch=async()=>{throw new TypeError('fixture network');};
await assert.rejects(api('/auth/login'),/could not finish signing you in/);
await assert.rejects(api('/auth/register'),/could not confirm account creation/);
const abort=new DOMException('fixture explicit cancellation','AbortError');
globalThis.fetch=async()=>{throw abort;};
await assert.rejects(api('/auth/login',{signal:controller.signal}),error=>error===abort);
globalThis.fetch=async()=>({ok:false,status:401,json:async()=>({error:{message:'Invalid fixture credentials'}})});
await assert.rejects(api('/auth/login'),error=>error.status===401&&error.message==='Invalid fixture credentials');
AbortSignal.timeout=original;
console.log('PASS auth cold-start budget75s; market budget20s; explicit startup cancellation preserved');

console.log('PASS auth timeout/network uncertainty; registration not blindly replayed; one request only; explicit abort and 401 preserved');
