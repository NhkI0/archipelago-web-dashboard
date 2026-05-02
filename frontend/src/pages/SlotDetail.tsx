import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { SlotDetail as SlotDetailT, api } from "../api";
import ProgressBar from "../components/ProgressBar";
import BadgePill from "../components/BadgePill";

type Filter = "all" | "remaining" | "checked" | "hinted";

export default function SlotDetail() {
  const { name = "" } = useParams();
  const [data, setData] = useState<SlotDetailT | null>(null);
  const [filter, setFilter] = useState<Filter>("remaining");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.slot(name).then(setData).catch(console.error);
  }, [name]);

  const hintedLocIds = useMemo(
    () => new Set((data?.hints || []).filter((h) => h.finding_slot === data?.slot.slot).map((h) => h.location_id)),
    [data],
  );

  const visible = useMemo(() => {
    if (!data) return [];
    return data.locations.filter((l) => {
      if (filter === "remaining" && l.checked) return false;
      if (filter === "checked" && !l.checked) return false;
      if (filter === "hinted" && !hintedLocIds.has(l.id)) return false;
      if (search && !l.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [data, filter, search, hintedLocIds]);

  if (!data) {
    return <div className="mx-auto max-w-[1200px] px-6 py-12 text-body">Loading…</div>;
  }

  const s = data.slot;

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-12">
      <Link to="/" className="text-body-sm text-mutedSoft hover:text-bodyStrong">← back</Link>

      <header className="mt-4 flex flex-wrap items-end gap-6 border-b hair pb-8">
        <div>
          <div className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 rounded-pill ${s.online ? "bg-semantic-success" : "bg-mutedSoft"}`} />
            <h1 className="text-display-md text-bodyStrong">{s.name}</h1>
            {s.goal_completed && <BadgePill tone="success">Goal</BadgePill>}
          </div>
          <div className="mt-1 font-mono text-body-sm text-body">{s.game}</div>
        </div>
        <div className="ml-auto flex items-end gap-8 text-body-sm">
          <Stat label="progress" value={`${s.percent.toFixed(1)}%`} />
          <Stat label="checks" value={`${s.checked} / ${s.total}`} />
          <Stat label="remaining" value={String(s.remaining)} />
          <Stat label="hint pts" value={String(s.hint_points)} />
          <Stat label="open hints" value={String(s.open_hints)} />
        </div>
      </header>

      <div className="mt-6 max-w-md"><ProgressBar value={s.checked} total={s.total} /></div>

      <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-[1fr,320px]">
        <section>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Tab active={filter === "all"} onClick={() => setFilter("all")}>All</Tab>
            <Tab active={filter === "remaining"} onClick={() => setFilter("remaining")}>Remaining</Tab>
            <Tab active={filter === "checked"} onClick={() => setFilter("checked")}>Checked</Tab>
            <Tab active={filter === "hinted"} onClick={() => setFilter("hinted")}>Hinted</Tab>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search locations…"
              className="ml-auto h-10 rounded-md bg-surface-card px-4 text-body-md text-bodyStrong placeholder:text-mutedSoft outline-none focus:ring-1 focus:ring-primary-glow"
            />
          </div>

          <ul className="divide-y hair-soft rounded-lg border hair bg-surface-card">
            {visible.map((l) => (
              <li key={l.id} className="flex items-center gap-3 px-4 py-3">
                <span
                  className={`h-1.5 w-1.5 rounded-pill ${l.checked ? "bg-semantic-success" : hintedLocIds.has(l.id) ? "bg-primary-glow" : "bg-hairline-strong"}`}
                />
                <span className={`text-body-sm ${l.checked ? "text-mutedSoft line-through" : "text-bodyStrong"}`}>
                  {l.name}
                </span>
                {l.item_name && (
                  <span className="ml-auto font-mono text-caption text-body">{l.item_name}</span>
                )}
              </li>
            ))}
            {visible.length === 0 && (
              <li className="px-4 py-8 text-center text-body-sm text-mutedSoft">No locations.</li>
            )}
          </ul>
        </section>

        <aside className="rounded-xl border hair bg-surface-card p-5">
          <h3 className="text-title-md text-bodyStrong">Hints</h3>
          <p className="mt-1 text-body-sm text-mutedSoft">Items the world has revealed for this slot.</p>
          <ul className="mt-4 space-y-3">
            {data.hints.map((h, i) => (
              <li key={i} className="rounded-md bg-canvas-deep p-3">
                <div className="text-caption text-body">
                  {h.finding_slot === s.slot ? "you find" : "you receive"}
                </div>
                <div className="text-body-sm text-bodyStrong">{h.item_name}</div>
                <div className="font-mono text-caption text-mutedSoft">{h.location_name}</div>
                <div className="mt-2">
                  <BadgePill tone={h.found ? "success" : "primary"}>
                    {h.found ? "found" : "open"}
                  </BadgePill>
                </div>
              </li>
            ))}
            {data.hints.length === 0 && (
              <li className="text-body-sm text-mutedSoft">None yet.</li>
            )}
          </ul>
        </aside>
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

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`h-9 rounded-md px-4 text-btn transition-colors ${
        active ? "bg-primary text-white" : "bg-surface-card text-body hover:text-bodyStrong"
      }`}
    >
      {children}
    </button>
  );
}
