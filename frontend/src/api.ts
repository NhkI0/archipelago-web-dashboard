import * as demo from "./demo/store";

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

// Tag ids are host-configurable (see config.toml / /api/config), so this is an
// open string rather than a fixed union.
export type HintTag = string;

export type Hint = {
  finding_slot: number;
  receiving_slot: number;
  item_id: number;
  location_id: number;
  item_name: string;
  location_name: string;
  found: boolean;
  tag: HintTag | "";
};

export type Snapshot = {
  seed_name: string;
  slots: Slot[];
  hints: Hint[];
  hint_cost: number;
  totals: { total_locations: number; total_checked: number };
};

export type DeathRow = { name: string; deaths: number };
export type Deaths = { available: boolean; rows: DeathRow[] };

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
  received_items: ReceivedItem[];
};

export type ReceivedItem = {
  item_name: string;
  location_name: string;
  sender: string;
  timestamp: number | null;
};

export type Me =
  | { logged_in: false }
  | { logged_in: true; slot: string; hint_points: number; last_text: string };

const j = async <T,>(r: Response): Promise<T> => {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json() as Promise<T>;
};

export type LoginReason = "invalid_slot" | "invalid_password" | "unreachable" | "unknown";

export class LoginError extends Error {
  status: number;
  reason: LoginReason;
  constructor(status: number, reason: LoginReason, detail: string) {
    super(detail);
    this.status = status;
    this.reason = reason;
  }
}

function loginReason(status: number, detail: string): LoginReason {
  const d = detail.toLowerCase();
  if (status === 503 || d.includes("unreachable")) return "unreachable";
  if (d.includes("password")) return "invalid_password";
  if (status === 404 || d.includes("invalidslot") || d.includes("invalidgame") || d.includes("unknown slot"))
    return "invalid_slot";
  return "unknown";
}

async function loginErrorDetail(r: Response): Promise<string> {
  try {
    const body = await r.clone().json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    // fall through to text
  }
  return (await r.text()) || r.statusText;
}

export type TagDef = { id: string; label: string; label_fr?: string; emoji?: string };

export type HallOfFameEntry = { file: string; artist: string; date: string; title?: string | null };

export type SiteConfig = {
  branding: {
    hero_title: string;
    hero_image: string;
    hero_image_fade: number;
    loading_name: string;
  };
  footer: { left: string; right: string };
  features: { hall_of_fame: boolean; death_leaderboard: boolean; constellation: boolean };
  hints: { blocked_tag: string; tags: TagDef[] };
};

const realApi = {
  config: () => fetch("/api/config").then(j<SiteConfig>),
  hallOfFame: () => fetch("/api/hall_of_fame").then(j<HallOfFameEntry[]>),
  state: () => fetch("/api/state").then(j<Snapshot>),
  deaths: () => fetch("/api/deaths").then(j<Deaths>),
  slot: (name: string) => fetch(`/api/slot/${encodeURIComponent(name)}`).then(j<SlotDetail>),
  me: () => fetch("/api/me").then(j<Me>),
  login: async (slot: string, password: string) => {
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ slot, password }),
    });
    if (!r.ok) {
      const detail = await loginErrorDetail(r);
      throw new LoginError(r.status, loginReason(r.status, detail), detail);
    }
    return r.json() as Promise<{ ok: true; slot: string; game: string; hint_points: number }>;
  },
  logout: () => fetch("/api/logout", { method: "POST" }).then(j),
  hint: (kind: "item" | "location", target: string) =>
    fetch("/api/hint", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ kind, target }),
    }).then(j<{ ok: boolean; reply?: string; queued?: boolean; hint_points: number; error?: string }>),
  hintTag: (h: Pick<Hint, "finding_slot" | "receiving_slot" | "item_id" | "location_id">, tag: HintTag | "") =>
    fetch("/api/hint_tag", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        finding_slot: h.finding_slot,
        receiving_slot: h.receiving_slot,
        item_id: h.item_id,
        location_id: h.location_id,
        tag,
      }),
    }).then(j<{ ok: boolean; tag: string }>),
};

function realLiveSocket(onEvent: (e: any) => void): () => void {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws/live`);
  ws.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {}
  };
  return () => ws.close();
}

// The static "try it" build (VITE_DEMO=1) swaps the whole backend for an
// in-memory mock; the production build keeps the real fetch/WebSocket client.
// VITE_DEMO is a compile-time literal, so the unused branch (and the demo store
// + its sample data) is dead-code-eliminated from production bundles.
export const IS_DEMO = !!import.meta.env.VITE_DEMO;

export const api = IS_DEMO ? demo.demoApi : realApi;
export const liveSocket = IS_DEMO ? demo.demoLiveSocket : realLiveSocket;
