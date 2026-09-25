// In-memory demo backend. Powers the static "try it" build (VITE_DEMO=1): the
// same api surface as ../api, but every call reads/writes module-level state
// with no network. Because the module re-initialises on each page load, all
// changes (hints, tags, login) reset on reload, exactly the view-only demo the
// site advertises. See ../api.ts for where this is swapped in.
import { DEFAULT_CONFIG } from "../config";
import { HALL_OF_FAME } from "./hallOfFame";
import {
  AvailableSlot,
  Deaths,
  HallOfFameEntry,
  Hint,
  HintTag,
  LoginError,
  Me,
  MySlot,
  SiteConfig,
  Slot,
  SlotDetail,
  Snapshot,
  TrackerMineSlot,
  TrackerResult,
} from "../api";

// The tracker tab has no real backend to run against here either, but it's
// fully mockable from data this store already has, so the demo shows it off too rather than hiding it
// (see demoTrackerApi below).
const config: SiteConfig = { ...DEFAULT_CONFIG, tracker: { enabled: true } };

type Base = { slot: number; name: string; game: string; total: number; checked: number; hint_points: number };

// Slots + hints below are lifted from a real multiworld spoiler so item↔game
// pairings are genuine.
const BASE: Base[] = [
  { slot: 1, name: "BOUZINFURTIF", game: "Portal 2", total: 63, checked: 41, hint_points: 35 },
  { slot: 2, name: "nagumo", game: "Minecraft", total: 92, checked: 58, hint_points: 22 },
  { slot: 3, name: "JDLoGin", game: "Cuphead", total: 80, checked: 80, hint_points: 12 },
  { slot: 4, name: "TéLEAchat", game: "Don't Starve Together", total: 110, checked: 33, hint_points: 27 },
  { slot: 5, name: "Dopamine", game: "Satisfactory", total: 120, checked: 72, hint_points: 30 },
];

const HINT_COST = 10;
let seq = 1000;

// Real placements from the spoiler (finder → receiver, item, location). Every
// item belongs to its receiver's game, no cross-game mismatches.
let hints: Hint[] = [
  h(1, 2, "Archery", "Secret Panel Completion", false, "mandatory"),
  h(1, 3, "Coin", "Turret Intro Completion", true, ""),
  h(1, 4, "Feather Pencil", "Dual Lasers Completion", false, "comfort"),
  h(4, 3, "Super Art II", "Honey Nuggets", false, ""),
  h(3, 2, "4 Emeralds", "Porkrind's Emporium Charm 3", false, "bked"),
  h(4, 2, "Dragon Egg Shard", "Bee", true, ""),
  h(3, 1, "Moon Dust", "Treetop Trouble Coin 5", false, ""),
  h(4, 1, "Lemon", "Clockwork Rook", false, "comfort"),
  h(1, 5, "Recipe: AI Expansion Server", "Wake Up Completion", false, "bked"),
  h(5, 2, "Spyglass", "Hub 1-1, item 3", false, ""),
];

function h(finding: number, receiving: number, item: string, loc: string, found: boolean, tag: HintTag): Hint {
  return {
    finding_slot: finding,
    receiving_slot: receiving,
    item_id: seq++,
    location_id: seq++,
    item_name: item,
    location_name: loc,
    found,
    tag,
  };
}

// Demo login supports several slots at once, mirroring the real backend's bag.
let currentSlots: string[] = [];
const listeners = new Set<(e: unknown) => void>();

function baseOf(name: string): Base | undefined {
  return BASE.find((b) => b.name === name);
}

function mySlotOf(b: Base): MySlot {
  return { slot: b.name, slot_num: b.slot, hint_points: b.hint_points, last_text: "" };
}

function meObj(): Me {
  const slots = currentSlots.map(baseOf).filter((b): b is Base => !!b).map(mySlotOf);
  return slots.length > 0 ? { logged_in: true, slots } : { logged_in: false, slots: [] };
}

function openHintsFor(slot: number): number {
  return hints.filter((x) => !x.found && x.finding_slot === slot).length;
}

function slotObj(b: Base): Slot {
  return {
    slot: b.slot,
    name: b.name,
    game: b.game,
    total: b.total,
    checked: b.checked,
    remaining: Math.max(0, b.total - b.checked),
    percent: b.total ? (100 * b.checked) / b.total : 0,
    online: currentSlots.includes(b.name),
    hint_points: b.hint_points,
    goal_completed: b.checked >= b.total,
    open_hints: openHintsFor(b.slot),
  };
}

function snapshot(): Snapshot {
  const slots = BASE.map(slotObj);
  return {
    seed_name: "DEMO-SEED",
    slots,
    hints,
    hint_cost: HINT_COST,
    server: { host: "demo.archipelago.local", port: 38281, connected: true },
    totals: {
      total_locations: slots.reduce((a, s) => a + s.total, 0),
      total_checked: slots.reduce((a, s) => a + s.checked, 0),
    },
  };
}

function emit(type: string) {
  const snap = snapshot();
  for (const l of listeners) l({ type, snapshot: snap });
}

// Items belong to a game, so a slot only ever receives items from its own game.
const GAME_ITEMS: Record<string, string[]> = {
  "Portal 2": ["Slice of Cake", "Moon Dust", "Lemon", "Weighted Cubes", "Turrets"],
  Minecraft: ["Dragon Egg Shard", "50 XP", "4 Emeralds", "16 Porkchops", "32 Arrows", "16 Iron Ore"],
  Cuphead: ["Coin", "Soul Contract", "Super Charge", "+1 Health", "Super Art II", "Whetstone"],
  "Don't Starve Together": ["Boss Defeat", "Wood Wall", "Winter Hat", "Weather Pain", "Glossamer Saddle", "Moggles"],
  Satisfactory: ["Small Inflated Pocket Dimension", "Pulse Nobelisk", "Packaged Oil", "Ficsite Trigon", "Expanded Toolbelt", "Computer"],
};
const gameItems = (game: string): string[] => GAME_ITEMS[game] ?? ["Reward A", "Reward B", "Reward C"];

// Some items have several copies still to hint, so the "Hint an item" tab shows
// its ×N count badge (e.g. Coin ×4 for Cuphead, after one Coin is already
// hinted, 5 available - 1 hinted = 4 shown).
const AVAIL_COUNTS = [5, 2, 1, 1, 1, 1];
const availableFor = (game: string): string[] =>
  gameItems(game).flatMap((item, i) => Array<string>(AVAIL_COUNTS[i] ?? 1).fill(item));

function detail(name: string): SlotDetail {
  const s = baseOf(name) ?? BASE[0];
  const slot = slotObj(s);
  const others = BASE.filter((x) => x.slot !== s.slot);
  const locations = Array.from({ length: s.total }, (_, i) => {
    const recipient = BASE[i % BASE.length];
    return {
      id: 1 + i,
      name: `${s.game}: Check ${i + 1}`,
      checked: i < s.checked,
      item_for_slot: recipient.slot,
      // A checked location has yielded an item for its recipient's own game.
      item_name: i < s.checked ? gameItems(recipient.game)[i % gameItems(recipient.game).length] : null,
    };
  });
  // Items this slot has RECEIVED are for this slot's own game, and all carry a
  // real timestamp so the "before tracking started" label never appears.
  const pool = gameItems(s.game);
  const now = Date.now() / 1000;
  const received_items = others.slice(0, 2).map((o, i) => ({
    item_name: pool[i % pool.length],
    location_name: `${o.game}: Check ${i + 3}`,
    sender: o.name,
    timestamp: now - (i + 1) * 1800,
  }));
  return {
    slot,
    locations,
    hints: hints.filter((x) => x.finding_slot === s.slot || x.receiving_slot === s.slot),
    available_items: availableFor(s.game),
    received_items,
  };
}

export const demoApi = {
  config: async (): Promise<SiteConfig> => config,
  // The demo has no backend to serve host-dropped images from, so it keeps
  // using the bundled sample entries/images instead of hitting /api.
  hallOfFame: async (): Promise<HallOfFameEntry[]> => HALL_OF_FAME,
  state: async (): Promise<Snapshot> => snapshot(),
  deaths: async (): Promise<Deaths> => ({
    available: true,
    rows: [
      { name: "nagumo", deaths: 27 },
      { name: "TéLEAchat", deaths: 14 },
      { name: "BOUZINFURTIF", deaths: 9 },
    ],
  }),
  slot: async (name: string): Promise<SlotDetail> => detail(name),
  me: async (): Promise<Me> => meObj(),
  login: async (slot: string, _password: string) => {
    const b = baseOf(slot);
    if (!b) throw new LoginError(404, "invalid_slot", "No slot found with that name.");
    currentSlots = [slot];
    emit("room_update");
    return meObj() as Extract<Me, { logged_in: true }>;
  },
  logout: async () => {
    currentSlots = [];
    emit("room_update");
    return { ok: true };
  },
  slotsAvailable: async (): Promise<{ slots: AvailableSlot[] }> => ({
    slots: BASE.map((b) => ({ name: b.name, connected: currentSlots.includes(b.name) })),
  }),
  slotsAdd: async (slot: string) => {
    const b = baseOf(slot);
    if (!b) throw new LoginError(404, "invalid_slot", "No slot found with that name.");
    if (!currentSlots.includes(slot)) currentSlots = [...currentSlots, slot];
    emit("room_update");
    return meObj() as Extract<Me, { logged_in: true }>;
  },
  slotsRemove: async (slot: string): Promise<Me> => {
    currentSlots = currentSlots.filter((s) => s !== slot);
    emit("room_update");
    return meObj();
  },
  hint: async (
    slot: string,
    kind: "item" | "location",
    target: string,
  ): Promise<{ ok: boolean; reply?: string; queued?: boolean; hint_points: number; error?: string }> => {
    const b = baseOf(slot);
    const me = b?.slot ?? 1;
    const other = BASE.find((x) => x.slot !== me)?.slot ?? me;
    const rec =
      kind === "item"
        ? h(other, me, target, "Somewhere in the multiworld", false, "")
        : h(me, other, "Mystery item", target, false, "");
    hints = [...hints, rec];
    if (b) b.hint_points = Math.max(0, b.hint_points - Math.ceil((HINT_COST / 100) * (b.total || 0)));
    emit("hint");
    return { ok: true, reply: `(demo) hinted ${target}`, hint_points: b?.hint_points ?? 0 };
  },
  hintTag: async (
    hh: Pick<Hint, "finding_slot" | "receiving_slot" | "item_id" | "location_id">,
    tag: HintTag | "",
  ) => {
    const rec = hints.find(
      (x) =>
        x.finding_slot === hh.finding_slot &&
        x.receiving_slot === hh.receiving_slot &&
        x.item_id === hh.item_id &&
        x.location_id === hh.location_id,
    );
    if (rec) rec.tag = tag;
    hints = [...hints];
    emit("hints_replaced");
    return { ok: true, tag };
  },
};

// Which logged-in slots have "uploaded" a YAML in this demo session; resets on reload.
const yamlUploaded = new Set<string>();

export const demoTrackerApi = {
  mine: async (): Promise<{ slots: TrackerMineSlot[] }> => ({
    slots: currentSlots.map((slot) => ({ slot, has_yaml: yamlUploaded.has(slot) })),
  }),
  uploadYaml: async (slot: string, _file: File): Promise<{ ok: true }> => {
    yamlUploaded.add(slot);
    return { ok: true };
  },
  run: async (slot: string): Promise<TrackerResult> => {
    const d = detail(slot);
    const remaining = d.locations.filter((l) => !l.checked);
    // No real game logic to run in the demo, so just flag roughly two thirds
    // of what's left as "accessible" to show both states in the list.
    const locations = remaining.map((l, i) => ({ id: l.id, name: l.name, accessible: i % 3 !== 0 }));
    return {
      slot,
      total: d.slot.total,
      checked: d.slot.checked,
      remaining: locations.length,
      accessible: locations.filter((l) => l.accessible).length,
      locations,
    };
  },
};

// Simulated checks so the Live Feed tab isn't empty in the demo build.
let demoCheckTimer: ReturnType<typeof setInterval> | null = null;

function emitDemoCheck() {
  const finder = BASE[Math.floor(Math.random() * BASE.length)];
  const others = BASE.filter((b) => b.slot !== finder.slot);
  const recv = Math.random() < 0.6 ? finder : others[Math.floor(Math.random() * others.length)];
  const pool = gameItems(recv.game);
  const checks = [{
    ts: Date.now() / 1000,
    finder_slot: finder.slot,
    recv_slot: recv.slot,
    finder_name: finder.name,
    recv_name: recv.name,
    finder_game: finder.game,
    recv_game: recv.game,
    item_name: pool[Math.floor(Math.random() * pool.length)],
    location_name: `${finder.game}: Check ${1 + Math.floor(Math.random() * finder.total)}`,
  }];
  for (const l of listeners) l({ type: "check", checks });
}

export function demoLiveSocket(onEvent: (e: unknown) => void, onStateChange?: (s: "open" | "reconnecting") => void): () => void {
  listeners.add(onEvent);
  onEvent({ type: "snapshot", snapshot: snapshot() });
  onStateChange?.("open"); // demo store has no real socket, so it's always "open"
  if (!demoCheckTimer) demoCheckTimer = setInterval(emitDemoCheck, 4000);
  return () => {
    listeners.delete(onEvent);
  };
}
