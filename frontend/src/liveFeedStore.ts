// Shared buffer outside any component, same pattern as Tracker.tsx's resultCache.
// The liveSocket subscription itself lives in components/LiveFeedCollector.tsx.

const MAX_ROWS = 300;

export type FeedItem =
  | { kind: "check"; id: string; ts: number; finder: string; finderGame: string; recv: string; recvGame: string; item: string; location: string }
  | { kind: "hint"; id: string; ts: number; finder: string; recv: string; item: string; location: string }
  | { kind: "goal"; id: string; ts: number; name: string; game: string };

let items: FeedItem[] = [];
let counter = 0;
// True once the collector's socket has delivered at least one message.
let ready = false;
const listeners = new Set<(items: FeedItem[]) => void>();

function notify() {
  for (const l of listeners) l(items);
}

export function subscribeFeed(listener: (items: FeedItem[]) => void): () => void {
  listeners.add(listener);
  listener(items);
  return () => listeners.delete(listener);
}

export function isFeedReady(): boolean {
  return ready;
}

export function markFeedReady(): void {
  if (ready) return;
  ready = true;
  notify();
}

export function pushFeedItem(item: FeedItem): void {
  items = [item, ...items].slice(0, MAX_ROWS);
  notify();
}

export function nextFeedId(prefix: string): string {
  return `${prefix}${counter++}`;
}
