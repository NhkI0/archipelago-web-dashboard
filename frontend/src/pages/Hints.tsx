import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Hint, Me, SlotDetail, Snapshot, api, liveSocket } from "../api";

type Tab = "location" | "item" | "hints";
type HintFilter = "mine_for" | "mine_in" | "all";

export default function Hints() {
  const [me, setMe] = useState<Me | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [detail, setDetail] = useState<SlotDetail | null>(null);
  const [tab, setTab] = useState<Tab>("item");
  const [hintFilter, setHintFilter] = useState<HintFilter>("mine_for");
  const [hideFound, setHideFound] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ kind: "item" | "location"; target: string } | null>(null);

  useEffect(() => {
    api.me().then(setMe);
    api.state().then(setSnap);
    return liveSocket((e) => {
      if (e?.snapshot) setSnap(e.snapshot);
    });
  }, []);

  useEffect(() => {
    if (me?.logged_in) api.slot(me.slot).then(setDetail);
  }, [me]);

  // Refresh slot detail when the live snapshot indicates new hints.
  useEffect(() => {
    if (me?.logged_in && snap) api.slot(me.slot).then(setDetail);
  }, [snap?.hints.length, me?.logged_in ? me.slot : null]);

  const slotNames = useMemo(() => {
    const m = new Map<number, string>();
    if (snap) for (const s of snap.slots) m.set(s.slot, s.name);
    return m;
  }, [snap]);

  const allItems = useMemo(() => {
    if (!detail) return [];
    const hinted = new Set(
      detail.hints
        .filter(h => h.receiving_slot === detail.slot.slot)
        .map(h => h.item_name)
    );
    return detail.available_items.filter(name => !hinted.has(name));
  }, [detail]);

  const remainingLocations = useMemo(() => {
    if (!detail) return [];
    const hinted = new Set(detail.hints.filter(h => h.finding_slot === detail.slot.slot).map(h => h.location_id));
    return detail.locations.filter(l => !l.checked && !hinted.has(l.id));
  }, [detail]);

  const visibleHints = useMemo(() => {
    if (!snap || !me || !me.logged_in) return [];
    const mySlot = detail?.slot.slot;
    let list: Hint[] = snap.hints;
    if (hintFilter === "mine_for") list = list.filter(h => h.receiving_slot === mySlot);
    else if (hintFilter === "mine_in") list = list.filter(h => h.finding_slot === mySlot);
    if (hideFound) list = list.filter(h => !h.found);
    const q = search.toLowerCase();
    if (q) list = list.filter(h =>
      h.item_name.toLowerCase().includes(q) ||
      h.location_name.toLowerCase().includes(q)
    );
    return list;
  }, [snap, me, detail, hintFilter, hideFound, search]);

  if (me === null || snap === null) {
    return <div className="mx-auto max-w-[1200px] px-6 py-12 text-body">Loading…</div>;
  }

  if (!me.logged_in) {
    return (
      <div className="mx-auto max-w-md px-6 py-section text-center">
        <h1 className="text-display-sm text-bodyStrong">Sign in to hint</h1>
        <p className="mt-2 text-body-sm text-body">
          Hints cost your slot's hint points, so you need to be logged in as that slot.
        </p>
        <Link
          to="/login"
          className="mt-6 inline-flex h-10 items-center rounded-md bg-primary px-5 text-btn text-white hover:bg-primary-active"
        >
          Sign in
        </Link>
      </div>
    );
  }

  function looksLikeFailure(reply: string | undefined): string | null {
    if (!reply) return null;
    const r = reply.toLowerCase();
    if (
      r.includes("not enough") ||
      r.includes("do not have") ||
      r.includes("cannot afford") ||
      r.includes("can't afford") ||
      r.includes("could not find") ||
      r.includes("ambiguous") ||
      r.includes("unknown") ||
      r.includes("no such") ||
      r.includes("already hinted")
    ) {
      return reply;
    }
    return null;
  }

  async function performSubmit(kind: "item" | "location", target: string) {
    setBusy(target);
    setError(null);
    try {
      const r = await api.hint(kind, target);
      const failure = r.error || looksLikeFailure(r.reply);
      if (failure) {
        setError(failure);
        return;
      }
      // Refresh state, jump to Hints tab so the user sees what was registered.
      await Promise.all([
        api.me().then(setMe),
        api.state().then(setSnap),
      ]);
      if (me && me.logged_in) api.slot(me.slot).then(setDetail);
      setTab("hints");
      setSearch("");
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  function requestSubmit(kind: "item" | "location", target: string) {
    setError(null);
    setConfirm({ kind, target });
  }

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-12">
      <header className="flex flex-wrap items-end gap-6 border-b hair pb-8">
        <div>
          <div className="text-caption-up uppercase text-primary-glow">Hint manager</div>
          <h1 className="mt-2 text-display-md text-bodyStrong">{me.slot}</h1>
        </div>
        <div className="ml-auto flex items-end gap-8 text-body-sm">
          <Stat label="hint pts" value={String(me.hint_points)} />
          {detail && <Stat label="checks" value={`${detail.slot.checked} / ${detail.slot.total}`} />}
          {detail && <Stat label="open hints" value={String(detail.slot.open_hints)} />}
        </div>
      </header>

      <div className="mt-8 flex flex-wrap gap-3">
        <Tab2 active={tab === "item"} onClick={() => setTab("item")}>Hint an item</Tab2>
        <Tab2 active={tab === "location"} onClick={() => setTab("location")}>Hint a location</Tab2>
        <Tab2 active={tab === "hints"} onClick={() => setTab("hints")}>
          Hints {snap.hints.length > 0 && <span className="ml-2 text-mutedSoft">{snap.hints.length}</span>}
        </Tab2>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter…"
          className="ml-auto h-10 w-64 rounded-md bg-surface-card px-4 text-body-md text-bodyStrong placeholder:text-mutedSoft outline-none focus:ring-1 focus:ring-primary-glow"
        />
      </div>

      {error && (
        <div className="mt-4 rounded-md bg-canvas-deep p-3 font-mono text-code text-semantic-error">
          {error}
        </div>
      )}

      <div className="mt-6 rounded-xl border hair bg-surface-card">
        {tab === "location" && (
          <ul className="divide-y hair-soft">
            {remainingLocations
              .filter((l) => l.name.toLowerCase().includes(search.toLowerCase()))
              .map((l) => (
                <li key={l.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="h-1.5 w-1.5 rounded-pill bg-hairline-strong" />
                  <span className="text-body-sm text-bodyStrong">{l.name}</span>
                  <button
                    onClick={() => requestSubmit("location", l.name)}
                    disabled={busy === l.name}
                    className="ml-auto h-8 rounded-md bg-primary px-3 text-btn text-white hover:bg-primary-active disabled:opacity-60"
                  >
                    {busy === l.name ? "…" : "Hint"}
                  </button>
                </li>
              ))}
            {remainingLocations.length === 0 && (
              <li className="px-4 py-8 text-center text-body-sm text-mutedSoft">
                No remaining locations to hint.
              </li>
            )}
          </ul>
        )}

        {tab === "item" && (
          <ul className="divide-y hair-soft">
            {allItems
              .filter((n) => n.toLowerCase().includes(search.toLowerCase()))
              .map((name) => (
                <li key={name} className="flex items-center gap-3 px-4 py-3">
                  <span className="h-1.5 w-1.5 rounded-pill bg-hairline-strong" />
                  <span className="text-body-sm text-bodyStrong">{name}</span>
                  <button
                    onClick={() => requestSubmit("item", name)}
                    disabled={busy === name}
                    className="ml-auto h-8 rounded-md bg-primary px-3 text-btn text-white hover:bg-primary-active disabled:opacity-60"
                  >
                    {busy === name ? "…" : "Hint"}
                  </button>
                </li>
              ))}
            {allItems.length === 0 && (
              <li className="px-4 py-8 text-center text-body-sm text-mutedSoft">
                No items left to hint.
              </li>
            )}
          </ul>
        )}

        {tab === "hints" && (
          <div>
            <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b hair-soft">
              <SubTab active={hintFilter === "mine_for"} onClick={() => setHintFilter("mine_for")}>For my world</SubTab>
              <SubTab active={hintFilter === "mine_in"} onClick={() => setHintFilter("mine_in")}>In my world</SubTab>
              <SubTab active={hintFilter === "all"} onClick={() => setHintFilter("all")}>All</SubTab>
              <Toggle
                className="ml-auto"
                label="Hide found"
                checked={hideFound}
                onChange={setHideFound}
              />
            </div>
            <div className="grid grid-cols-[1fr_1fr_auto_auto] gap-x-4 px-4 py-2 text-caption-up uppercase text-mutedSoft border-b hair-soft">
              <div>Item</div>
              <div>Location</div>
              <div>Finder → Receiver</div>
              <div>Status</div>
            </div>
            <ul className="divide-y hair-soft">
              {visibleHints.map((h, i) => {
                const finder = slotNames.get(h.finding_slot) ?? `slot ${h.finding_slot}`;
                const receiver = slotNames.get(h.receiving_slot) ?? `slot ${h.receiving_slot}`;
                return (
                  <li
                    key={`${h.finding_slot}:${h.receiving_slot}:${h.item_id}:${h.location_id}:${i}`}
                    className="grid grid-cols-[1fr_1fr_auto_auto] items-center gap-x-4 px-4 py-3 text-body-sm"
                  >
                    <span className="text-bodyStrong">{h.item_name}</span>
                    <span className="text-body">{h.location_name}</span>
                    <span className="text-mutedSoft tabular-nums">{finder} → {receiver}</span>
                    <span className={`inline-flex h-6 items-center rounded-pill px-2 text-caption-up uppercase ${
                      h.found ? "bg-semantic-success/20 text-semantic-success" : "bg-canvas-deep text-mutedSoft"
                    }`}>
                      {h.found ? "found" : "open"}
                    </span>
                  </li>
                );
              })}
              {visibleHints.length === 0 && (
                <li className="px-4 py-8 text-center text-body-sm text-mutedSoft">
                  {hintFilter === "mine_for" && "No hints for items you'll receive yet."}
                  {hintFilter === "mine_in" && "No hints in your world yet."}
                  {hintFilter === "all" && "No hints anywhere yet."}
                </li>
              )}
            </ul>
          </div>
        )}
      </div>

      {confirm && (() => {
        const total = detail?.slot.total ?? 0;
        const pct = snap.hint_cost ?? 10;
        const cost = Math.max(1, Math.ceil((pct / 100) * total));
        const enough = me.hint_points >= cost;
        return (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => !busy && setConfirm(null)}
        >
          <div
            className="w-full max-w-md rounded-xl border hair bg-surface-card p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-title-md text-bodyStrong">Confirm hint</h2>
            <p className="mt-2 text-body-sm text-body">
              Hint {confirm.kind === "item" ? "item" : "location"}{" "}
              <span className="text-bodyStrong">{confirm.target}</span>?
            </p>
            <div className="mt-4 grid grid-cols-3 gap-3 text-body-sm">
              <Stat label="cost" value={`~${cost}`} />
              <Stat label="balance" value={String(me.hint_points)} />
              <Stat label="after" value={enough ? String(me.hint_points - cost) : "—"} />
            </div>
            <div className="mt-3 text-body-sm text-mutedSoft">
              Server hint cost is <span className="text-bodyStrong tabular-nums">{pct}%</span> of your total checks.
              {!enough && <span className="ml-1 text-semantic-error">Not enough hint points.</span>}
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setConfirm(null)}
                disabled={!!busy}
                className="h-10 rounded-md bg-canvas-deep px-5 text-btn text-body hover:text-bodyStrong disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  const c = confirm;
                  await performSubmit(c.kind, c.target);
                  setConfirm(null);
                }}
                disabled={!!busy || !enough}
                className="h-10 rounded-md bg-primary px-5 text-btn text-white hover:bg-primary-active disabled:opacity-60"
              >
                {busy ? "Sending…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
        );
      })()}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-caption text-mutedSoft uppercase tracking-[0.08em]">{label}</div>
      <div className="text-title-md text-bodyStrong tabular-nums">{value}</div>
    </div>
  );
}

function Tab2({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`h-10 rounded-md px-5 text-btn transition-colors ${
        active ? "bg-primary text-white" : "bg-surface-card text-body hover:text-bodyStrong"
      }`}
    >
      {children}
    </button>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  className = "",
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  className?: string;
}) {
  return (
    <label className={`inline-flex cursor-pointer items-center gap-3 text-body-sm text-body select-none ${className}`}>
      <span>{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-pill border hair transition-colors ${
          checked ? "bg-primary border-primary" : "bg-canvas-deep"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-pill bg-white shadow transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </label>
  );
}

function SubTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`h-7 rounded-pill px-3 text-caption-up uppercase tracking-wider transition-colors ${
        active ? "bg-primary text-white" : "bg-canvas-deep text-mutedSoft hover:text-bodyStrong"
      }`}
    >
      {children}
    </button>
  );
}
