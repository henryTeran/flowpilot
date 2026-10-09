// FlowPilot adapter: use the installed upstream broker, never a replacement router.
import { routeRequest, contextPack } from '@ai-swiss/base';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
const root = fileURLToPath(new URL('./workspace/', import.meta.url));
let input = '';
for await (const chunk of process.stdin) {
  input += chunk;
  if (Buffer.byteLength(input) > 16000) throw new Error('Input too large');
}
try {
  const installed = JSON.parse(await readFile(new URL('./node_modules/@ai-swiss/base/package.json', import.meta.url), 'utf8'));
  if (installed.version !== '1.5.1') throw new Error('Unexpected BASE version');
  const request = JSON.parse(input);
  if (Object.keys(request).join() !== 'message' || typeof request.message !== 'string' ||
      !request.message.trim() || Array.from(request.message).length > 2000) throw new Error('Invalid request');
  // Pin the documented deterministic mode; machine Studio model settings cannot
  // introduce a remote dependency into this read-first application boundary.
  const route = await routeRequest(root, request.message, {
    embeddingStrategy: { readRouting: async () => null },
  });
  const processId = route.status === 'routed' ? route.process?.id : null;
  // Context is metadata only; never expose corpus bodies or provider prompts.
  const context = processId ? await contextPack(root, processId) : null;
  process.stdout.write(JSON.stringify({
    status: route.status === 'routed' ? 'routed' : 'clarification',
    process_id: processId,
    framework_version: '1.5.1',
    request_digest: createHash('sha256').update(request.message, 'utf8').digest('hex'),
    context_prepared: context !== null,
  }));
} catch {
  process.stderr.write('BASE upstream routing unavailable or invalid');
  process.exitCode = 1;
}
