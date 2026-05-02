import { useEffect, useState } from "react";
import { Snapshot, api, liveSocket } from "../api";
import Hero from "../components/Hero";
import SlotCard from "../components/SlotCard";

export default function Dashboard() {
  const [snap, setSnap] = useState<Snapshot | null>(null);

  useEffect(() => {
    api.state().then(setSnap).catch(console.error);
    return liveSocket((e) => {
      if (e?.snapshot) setSnap(e.snapshot);
    });
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
    </>
  );
}
