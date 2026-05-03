import { useEffect, useState } from "react";
import { Deaths, Snapshot, api, liveSocket } from "../api";
import Hero from "../components/Hero";
import SlotCard from "../components/SlotCard";

export default function Dashboard() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [deaths, setDeaths] = useState<Deaths | null>(null);

  useEffect(() => {
    api.state().then(setSnap).catch(console.error);
    api.deaths().then(setDeaths).catch(() => {});
    return liveSocket((e) => {
      if (e?.snapshot) setSnap(e.snapshot);
    });
  }, []);

  // Refresh deaths periodically (the TUI updates the JSON file).
  useEffect(() => {
    const id = setInterval(() => {
      api.deaths().then(setDeaths).catch(() => {});
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  if (!snap) {
    return (
      <div className="mx-auto max-w-[1200px] px-6 py-section text-body">Loading…</div>
    );
  }

  return (
    <>
      <Hero
        seed={snap.seed_name}
        totalChecked={snap.totals.total_checked}
        totalLocations={snap.totals.total_locations}
        slots={snap.slots.length}
        hints={snap.hints.filter((h) => !h.found).length}
      />
      <section className="mx-auto max-w-[1200px] px-6 py-section">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <div className="text-caption-up uppercase text-primary-glow">Slots</div>
            <h2 className="mt-2 text-display-md text-bodyStrong">Player progression</h2>
          </div>
          <div className="text-body-sm text-mutedSoft">{snap.slots.length} active</div>
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {snap.slots.map((s) => <SlotCard key={s.slot} slot={s} />)}
        </div>
      </section>

      {deaths?.available && deaths.rows.length > 0 && (
        <section className="mx-auto max-w-[1200px] px-6 pb-section">
          <div className="mb-6 flex items-end justify-between">
            <div>
              <div className="text-caption-up uppercase text-primary-glow">Death leaderboard</div>
              <h2 className="mt-2 text-display-md text-bodyStrong">Most spectacular failures</h2>
            </div>
            <div className="text-body-sm text-mutedSoft">{deaths.rows.length} contender{deaths.rows.length === 1 ? "" : "s"}</div>
          </div>
          <ol className="rounded-xl border hair bg-surface-card divide-y hair-soft">
            {deaths.rows.slice(0, 10).map((row, i) => (
              <li key={row.name} className="flex items-center gap-4 px-4 py-3">
                <span className="w-6 text-mutedSoft tabular-nums">{i + 1}.</span>
                <span className="flex-1 text-body-sm text-bodyStrong">{row.name}</span>
                <span className="font-mono tabular-nums text-body">{row.deaths}</span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </>
  );
}
