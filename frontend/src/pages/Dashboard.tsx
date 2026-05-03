import { useEffect, useState } from "react";
import { Deaths, Snapshot, api, liveSocket } from "../api";
import Hero from "../components/Hero";
import SlotCard from "../components/SlotCard";
import Constellation from "../components/Constellation";
import { useT } from "../i18n";

export default function Dashboard() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [deaths, setDeaths] = useState<Deaths | null>(null);
  const { t } = useT();

  useEffect(() => {
    api.state().then(setSnap).catch(console.error);
    api.deaths().then(setDeaths).catch(() => {});
    return liveSocket((e) => {
      if (e?.snapshot) setSnap(e.snapshot);
    });
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      api.deaths().then(setDeaths).catch(() => {});
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  if (!snap) {
    return <div className="mx-auto max-w-[1200px] px-6 py-section text-slate">{t("common.loading")}</div>;
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
      <section className="mx-auto max-w-[1200px] px-6 pt-section">
        <div className="mb-10 text-center">
          <div className="text-caption-up uppercase text-primary">Multiworld map</div>
          <h2 className="mt-2 text-display-md text-ink">A constellation of {snap.slots.length} players</h2>
          <p className="mx-auto mt-3 max-w-xl text-body-md text-slate">
            Each avatar is a player; each thread is an item that has been hinted between two of their worlds.
          </p>
        </div>
        <Constellation
          slots={snap.slots}
          hints={snap.hints}
          totalChecked={snap.totals.total_checked}
          totalLocations={snap.totals.total_locations}
        />
      </section>

      <section className="mx-auto max-w-[1200px] px-6 py-section">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <div className="text-caption-up uppercase text-primary">{t("dash.kicker")}</div>
            <h2 className="mt-2 text-display-md text-ink">{t("dash.title")}</h2>
          </div>
          <div className="text-body-sm text-steel">{t("dash.active_n", { n: snap.slots.length })}</div>
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {snap.slots.map((s) => <SlotCard key={s.slot} slot={s} />)}
        </div>
      </section>

      {deaths?.available && deaths.rows.length > 0 && (
        <section className="mx-auto max-w-[1200px] px-6 pb-section">
          <div className="mb-6 flex items-end justify-between">
            <div>
              <div className="text-caption-up uppercase text-brand-orange">{t("deaths.kicker")}</div>
              <h2 className="mt-2 text-display-md text-ink">{t("deaths.title")}</h2>
            </div>
            <div className="text-body-sm text-steel">
              {t("deaths.contenders", { n: deaths.rows.length, plural: deaths.rows.length === 1 ? "" : "s" })}
            </div>
          </div>
          <ol className="rounded-lg border hair bg-canvas divide-y hair-soft">
            {deaths.rows.slice(0, 10).map((row, i) => (
              <li key={row.name} className="flex items-center gap-4 px-5 py-3">
                <span className="w-6 text-stone tabular-nums">{i + 1}.</span>
                <span className="flex-1 text-body-sm text-ink font-medium">{row.name}</span>
                <span className="font-mono tabular-nums text-slate">{row.deaths}</span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </>
  );
}
