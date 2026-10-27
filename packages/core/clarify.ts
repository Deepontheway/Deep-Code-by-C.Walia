export async function clarifyIfNeeded(goal: string) {
  console.log('[CLARIFY] Got it. Just to make sure I build exactly what you want...');
  console.log('[CLARIFY] Can you explain a bit more about:', goal);
  console.log('[CLARIFY] Like: features, design look, platform (web/app/android), or anything specific?');
  return true;
}
