import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Me, SlotDetail, Snapshot, api } from "../api";

type Tab = "location" | "item";

export default function Hints() {
  const [me, setMe] = useState<Me | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [detail, setDetail] = useState<SlotDetail | null>(null);
  const [tab, setTab] = useState<Tab>("location");
  const [search, setSearch] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.me().then(setMe);
    api.state().then(setSnap);
  }, []);

  useEffect(() => {
    if (me?.logged_in) api.slot(me.slot).then(setDetail);
  }, [me]);

  // ── Build candidate lists (must run before any early returns to satisfy hooks rules) ──
  const allItems = useMemo(() => {
    if (!snap) return [];
    const set = new Set<string>();
    for (const slot of snap.slots) {
      for (const h of snap.hints) {
        if (h.receiving_slot === slot.slot) set.add(h.item_name);
      }
    }
    return Array.from(set).sort();
  }, [snap]);

  const remainingLocations = useMemo(() => {
    if (!detail) return [];
    const hinted = new Set(detail.hints.filter(h => h.finding_slot === detail.slot.slot).map(h => h.location_id));
    return detail.locations.filter(l => !l.checked && !hinted.has(l.id));
  }, [detail]);

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

  async function submit(kind: "item" | "location", target: string) {
    setBusy(target);
    setReply(null);
    try {
      const r = await api.hint(kind, target);
      if (r.error) setReply(`error: ${r.error}`);
      else setReply(r.reply ?? (r.queued ? "command sent" : "ok"));
      // Refresh balances
      api.me().then(setMe);
      if (me && me.logged_in) api.slot(me.slot).then(setDetail);
    } catch (e: any) {
      setReply(`error: ${e.message || e}`);
    } finally {
      setBusy(null);
    }
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

      <div className="mt-8 flex gap-3">
        <Tab2 active={tab === "location"} onClick={() => setTab("location")}>Hint a location</Tab2>
        <Tab2 active={tab === "item"} onClick={() => setTab("item")}>Hint an item</Tab2>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter…"
          className="ml-auto h-10 w-64 rounded-md bg-surface-card px-4 text-body-md text-bodyStrong placeholder:text-mutedSoft outline-none focus:ring-1 focus:ring-primary-glow"
        />
      </div>

      {reply && (
        <div className="mt-4 rounded-md bg-canvas-deep p-3 font-mono text-code text-body">{reply}</div>
      )}

      <div className="mt-6 rounded-xl border hair bg-surface-card">
        {tab === "location" ? (
          <ul className="divide-y hair-soft">
            {remainingLocations
              .filter((l) => l.name.toLowerCase().includes(search.toLowerCase()))
              .map((l) => (
                <li key={l.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="h-1.5 w-1.5 rounded-pill bg-hairline-strong" />
                  <span className="text-body-sm text-bodyStrong">{l.name}</span>
                  <button
                    onClick={() => submit("location", l.name)}
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
        ) : (
          <ul className="divide-y hair-soft">
            {allItems
              .filter((n) => n.toLowerCase().includes(search.toLowerCase()))
              .map((name) => (
                <li key={name} className="flex items-center gap-3 px-4 py-3">
                  <span className="h-1.5 w-1.5 rounded-pill bg-hairline-strong" />
                  <span className="text-body-sm text-bodyStrong">{name}</span>
                  <button
                    onClick={() => submit("item", name)}
                    disabled={busy === name}
                    className="ml-auto h-8 rounded-md bg-primary px-3 text-btn text-white hover:bg-primary-active disabled:opacity-60"
                  >
                    {busy === name ? "…" : "Hint"}
                  </button>
                </li>
              ))}
            {allItems.length === 0 && (
              <li className="px-4 py-8 text-center text-body-sm text-mutedSoft">
                No items in the index yet — type the exact item name in the AP client to hint freeform.
              </li>
            )}
          </ul>
        )}
      </div>
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
