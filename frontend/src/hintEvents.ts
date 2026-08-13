// Tiny pub/sub so the Hints confirm popup can close at the exact moment
// HintNotifier decides to show a toast for "a new hint landed for me" —
// tying both to the same call site instead of each re-deriving it from its
// own independent liveSocket snapshot (which could race).
type Listener = () => void;
const listeners = new Set<Listener>();

export function onNewHintForMe(cb: Listener): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function emitNewHintForMe(): void {
  listeners.forEach((cb) => cb());
}
