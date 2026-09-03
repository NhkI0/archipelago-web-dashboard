import * as demo from "./demo/store";
import { getBasePath } from "./basePath";

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

export type ServerStatus = { host: string; port: number; connected: boolean };

export type Snapshot = {
  seed_name: string;
  slots: Slot[];
  hints: Hint[];
  hint_cost: number;
  // True for archipelago.gg-polled rooms: hint_points below are a local
  // estimate (see server/room_poller.py), only accurate if every hint for
  // this room is requested through this dashboard.
  hint_points_estimated: boolean;
  server: ServerStatus;
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
  hint_points_estimated: boolean;
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

// "" at the root (self-hosted), "/<uuid>" for a hosted room -- every /api/*
// call must go through this, or a hosted room's requests land on the
// supervisor at the domain root instead of the room's own socket (verified
// on the real VPS 2026-08-26: absolute "/api/..." fetches 404'd once a room
// was actually reached via its "/<uuid>/" prefix through Caddy).
const apiUrl = (path: string) => getBasePath() + path;

const realApi = {
  config: () => fetch(apiUrl("/api/config")).then(j<SiteConfig>),
  hallOfFame: () => fetch(apiUrl("/api/hall_of_fame")).then(j<HallOfFameEntry[]>),
  state: () => fetch(apiUrl("/api/state")).then(j<Snapshot>),
  deaths: () => fetch(apiUrl("/api/deaths")).then(j<Deaths>),
  slot: (name: string) => fetch(apiUrl(`/api/slot/${encodeURIComponent(name)}`)).then(j<SlotDetail>),
  me: () => fetch(apiUrl("/api/me")).then(j<Me>),
  login: async (slot: string, password: string) => {
    const r = await fetch(apiUrl("/api/login"), {
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
  logout: () => fetch(apiUrl("/api/logout"), { method: "POST" }).then(j),
  hint: (kind: "item" | "location", target: string) =>
    fetch(apiUrl("/api/hint"), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ kind, target }),
    }).then(j<{ ok: boolean; reply?: string; queued?: boolean; hint_points: number; error?: string }>),
  hintTag: (h: Pick<Hint, "finding_slot" | "receiving_slot" | "item_id" | "location_id">, tag: HintTag | "") =>
    fetch(apiUrl("/api/hint_tag"), {
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

export type LiveSocketState = "open" | "reconnecting";

const RECONNECT_BASE_MS = 500;
const RECONNECT_MAX_MS = 10000;

function realLiveSocket(onEvent: (e: any) => void, onStateChange?: (s: LiveSocketState) => void): () => void {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  let ws: WebSocket | null = null;
  let stopped = false;
  let attempt = 0;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    ws = new WebSocket(`${proto}//${location.host}${getBasePath()}/ws/live`);
    ws.onopen = () => {
      attempt = 0;
      onStateChange?.("open");
    };
    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        if (parsed?.type === "ping") return; // keepalive only, not a UI event
        onEvent(parsed);
      } catch {}
    };
    const scheduleReconnect = () => {
      if (stopped) return;
      onStateChange?.("reconnecting");
      const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempt, RECONNECT_MAX_MS) * (0.75 + Math.random() * 0.5);
      attempt += 1;
      retryTimer = setTimeout(connect, delay);
    };
    ws.onclose = scheduleReconnect;
    ws.onerror = () => ws?.close();
  }
  connect();

  return () => {
    stopped = true;
    if (retryTimer) clearTimeout(retryTimer);
    ws?.close();
  };
}

// The static "try it" build (VITE_DEMO=1) swaps the whole backend for an
// in-memory mock; the production build keeps the real fetch/WebSocket client.
// VITE_DEMO is a compile-time literal, so the unused branch (and the demo store
// + its sample data) is dead-code-eliminated from production bundles.
export const IS_DEMO = !!import.meta.env.VITE_DEMO;

export const api = IS_DEMO ? demo.demoApi : realApi;
export const liveSocket = IS_DEMO ? demo.demoLiveSocket : realLiveSocket;
