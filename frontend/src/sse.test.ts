import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { parseSse } from './sse.js'
const bytes=(s:string)=>new ReadableStream({start(c){for(const b of new TextEncoder().encode(s))c.enqueue(Uint8Array.of(b));c.close()}})
const fixture=(n:string)=>readFile(new URL(`../../../../contracts/sse/${n}`,import.meta.url),'utf8')
const collect=async(s:string)=>{const out=[];for await(const e of parseSse(bytes(s)))out.push(e);return out}
test('frozen normal survives one-byte chunks',async()=>{const x=await collect(await fixture('v1-normal.sse'));assert.equal(x.at(-1)?.event,'done');assert.ok(x.find(e=>e.event==='sources')?.data.includes('"index":2'))})
test('frozen failed ends failed',async()=>{const x=await collect(await fixture('v1-failed.sse'));assert.ok(x.find(e=>e.event==='error'));assert.match(x.at(-1)?.data||'',/"status":"failed"/)})
test('frozen empty completes',async()=>assert.equal((await collect(await fixture('v1-empty.sse')).then(x=>x.at(-1)?.event)),'done'))
test('truncated rejects',async()=>await assert.rejects(async()=>collect(await fixture('v1-truncated.sse')),/done/))
test('cancellation is honored',async()=>{const c=new AbortController();c.abort();await assert.rejects(async()=>collectWithSignal(c.signal),/取消/)})
async function collectWithSignal(signal:AbortSignal){for await(const _ of parseSse(bytes('event: done\ndata: {"status":"completed"}\n\n'),signal)){} }

