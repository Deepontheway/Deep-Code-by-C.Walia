import { ensureBackend } from './backend.js';
import { startTUI } from './tui.js';

export async function runCli() {
  const backend = await ensureBackend();
  try {
    const instance = startTUI(backend.client);
    await instance.waitUntilExit();
  } finally {
    backend.stop();
  }
}
