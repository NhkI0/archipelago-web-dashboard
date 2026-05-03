export type Slot = {
  slot: number;
  name: string;
  game: string;
  total: number;
  checked: number;
  remaining: number;
  percent: number;
  online: boolean;
  hint_points: number;
  goal_completed: boolean;
  open_hints: number;
};

export type Hint = {
  finding_slot: number;
  receiving_slot: number;
  item_id: number;
  location_id: number;
  item_name: string;
  location_name: string;
  found: boolean;
};

export type Snapshot = {
  seed_name: string;
  slots: Slot[];
  hints: Hint[];
  totals: { total_locations: number; total_checked: number };
};

export type SlotDetail = {
  slot: Slot;
  locations: {
    id: number;
    name: string;
    checked: boolean;
    item_for_slot: number;
    item_name: string | null;
  }[];
  hints: Hint[];
  available_items: string[];
};

export type Me =
  | { logged_in: false }
  | { logged_in: true; slot: string; hint_points: number; last_text: string };

const j = async <T,>(r: Response): Promise<T> => {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json() as Promise<T>;
};

export const api = {
  state: () => fetch("/api/state").then(j<Snapshot>),
  slot: (name: string) => fetch(`/api/slot/${encodeURIComponent(name)}`).then(j<SlotDetail>),
  me: () => fetch("/api/me").then(j<Me>),
  login: (slot: string, password: string) =>
    fetch("/api/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ slot, password }),
    }).then(j<{ ok: true; slot: string; game: string; hint_points: number }>),
  logout: () => fetch("/api/logout", { method: "POST" }).then(j),
  hint: (kind: "item" | "location", target: string) =>
    fetch("/api/hint", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ kind, target }),
    }).then(j<{ ok: boolean; reply?: string; queued?: boolean; hint_points: number; error?: string }>),
};

export function liveSocket(onEvent: (e: any) => void): () => void {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws/live`);
  ws.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {}
  };
  return () => ws.close();
}
