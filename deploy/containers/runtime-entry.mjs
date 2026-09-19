// Trusted container bootstrap. The model has no file-reading or shell tool.
import { open, constants } from 'node:fs/promises';
import { createRuntimeServer } from './dist/src/server.js';
import { loadPolicy } from './dist/src/policy.js';
import { httpBroker } from './dist/src/broker.js';
import { httpContentBroker } from './dist/src/content-broker.js';

const file = await open('/run/secrets/runtime_token', constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
let token;
try {
  const info = await file.stat();
  if (!info.isFile() || info.uid !== process.getuid() || (info.mode & 0o077) || info.size > 128)
    throw new Error('runtime_credentials_invalid');
  const buffer = Buffer.alloc(129);
  const { bytesRead } = await file.read(buffer, 0, buffer.length, 0);
  token = buffer.subarray(0, bytesRead).toString('utf8');
  if (!/^[A-Za-z0-9_-]{43,128}$/.test(token)) throw new Error('runtime_credentials_invalid');
} finally {
  await file.close();
}
const policy = await loadPolicy(new URL('../research/', import.meta.url));
const server = createRuntimeServer({
  token, system: policy.system, policyDigest: policy.digest, pythonEnabled: policy.pythonEnabled,
  broker: capability => httpBroker('http://api:8000', capability),
  contentBroker: capability => httpContentBroker('http://api:8000', capability),
});
server.requestTimeout = 90000;
server.headersTimeout = 10000;
server.listen(8081, '0.0.0.0');
