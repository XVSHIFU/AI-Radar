import test from 'node:test'
import assert from 'node:assert/strict'
import { latestRequest } from './latest.js'
test('latest request ignores stale completion',()=>{const x=latestRequest();const a=x.begin(),b=x.begin();assert.ok(a.signal.aborted);assert.equal(a.current(),false);assert.equal(b.current(),true)})
