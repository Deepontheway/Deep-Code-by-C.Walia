import { MODELS, DEFAULT_MODEL, OLLAMA_BASE_URL } from '../../models/index.js';

export function routeModel(preferred?: string) {
  if (preferred) return preferred;
  return DEFAULT_MODEL;
}

export async function tryOllamaFallback() {
  try {
    const res = await fetch(OLLAMA_BASE_URL.replace('/v1','') + '/api/tags');
    if (res.ok) return { ok: true, model: 'qwen3-coder:14b' };
  } catch {}
  return { ok: false };
}
