import { useEffect, useMemo, useState } from "react";
import { Deaths, Me, Snapshot, api, liveSocket } from "../api";
import Hero from "../components/Hero";
import SlotCard from "../components/SlotCard";
import Constellation from "../components/Constellation";
import LoadingScreen, { markConnected } from "../components/LoadingScreen";
import { useT } from "../i18n";
import { useConfig, tagLabel } from "../config";

export default function Dashboard() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [deaths, setDeaths] = useState<Deaths | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [live, setLive] = useState<"open" | "reconnecting">("open");
  const { t, lang } = useT();
  const config = useConfig();
  const blockedTag = config.hints.blocked_tag;
  const blockedTagDef = config.hints.tags.find((tg) => tg.id === blockedTag);

  useEffect(() => {
    api.state().then(setSnap).catch(console.error);
    api.deaths().then(setDeaths).catch(() => {});
    api.me().then(setMe).catch(() => {});
    return liveSocket(
      (e) => {
        if (e?.snapshot) setSnap(e.snapshot);
      },
      setLive,
    );
  }, []);

  // Open BKed hints that involve the logged-in slot: both the checks they're
  // waiting on (as receiver) and the BKed checks sitting in their own world
  // that they can go find to unblock someone else (as finder).
  const bked = useMemo(() => {
    if (!snap || !me?.logged_in || !blockedTag) return [];
    const mySlot = snap.slots.find((s) => s.name === me.slot)?.slot;
    if (mySlot == null) return [];
    const names = new Map(snap.slots.map((s) => [s.slot, s.name]));
    return snap.hints
      .filter((h) => h.tag === blockedTag && !h.found && (h.receiving_slot === mySlot || h.finding_slot === mySlot))
      .map((h) => {
        const mine = h.receiving_slot === mySlot; // true: I'm waiting; false: it's in my world for someone
        return {
          ...h,
          mine,
          who: mine
            ? names.get(h.finding_slot) ?? `slot ${h.finding_slot}`
            : names.get(h.receiving_slot) ?? `slot ${h.receiving_slot}`,
        };
      });
  }, [snap, me]);

  useEffect(() => {
    const id = setInterval(() => {
      api.deaths().then(setDeaths).catch(() => {});
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (snap) markConnected();
  }, [snap]);

  if (!snap) {
    return <LoadingScreen />;
  }

  return (
    <>
      {live === "reconnecting" && (
        <div className="fixed left-1/2 top-3 z-50 -translate-x-1/2 rounded-pill bg-brand-orange px-3 py-1 text-caption-up uppercase text-white shadow-md">
          {t("dash.reconnecting")}
        </div>
      )}
      <Hero
        seed={snap.seed_name}
        totalChecked={snap.totals.total_checked}
        totalLocations={snap.totals.total_locations}
        slots={snap.slots.length}
        hints={snap.hints.filter((h) => !h.found).length}
        hintsFound={snap.hints.filter((h) => h.found).length}
        latestHint={snap.hints.length > 0 ? snap.hints[snap.hints.length - 1].item_name : null}
        server={snap.server}
      />

      {bked.length > 0 && (
        <section className="mx-auto max-w-[1200px] px-4 sm:px-6 pt-12 sm:pt-section">
          <div className="mb-6">
            <div className="text-caption-up uppercase text-brand-orange">{t("dash.bked.kicker")}</div>
            <h2 className="mt-2 text-display-sm sm:text-display-md text-ink">{t("dash.bked.title")}</h2>
            <p className="mt-2 max-w-xl text-body-sm text-slate">{t("dash.bked.intro")}</p>
          </div>
          <ul className="rounded-lg border border-brand-orange/30 bg-card-peach/40 dark:bg-brand-orange/10 divide-y hair-soft transition-colors duration-300">
            {bked.map((h, i) => (
              <li
                key={`${h.finding_slot}:${h.receiving_slot}:${h.item_id}:${h.location_id}:${i}`}
                className="flex flex-col gap-1.5 px-5 py-3 sm:flex-row sm:items-center sm:gap-4"
              >
                <span className="inline-flex h-6 w-fit items-center rounded-pill bg-brand-orange px-2.5 text-caption-up uppercase text-white">
                  {blockedTagDef ? `${blockedTagDef.emoji ? blockedTagDef.emoji + " " : ""}${tagLabel(blockedTagDef, lang)}` : blockedTag}
                </span>
                <span className="text-body-sm font-medium text-tintInk dark:text-ink">{h.item_name}</span>
                <span className="text-body-sm text-tintInkSoft dark:text-slate break-words">
                  {h.location_name} · {h.mine
                    ? t("dash.bked.finder", { finder: h.who })
                    : t("dash.bked.for_receiver", { receiver: h.who })}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {config.features.constellation && (
        <section className="mx-auto max-w-[1200px] px-4 sm:px-6 pt-12 sm:pt-section">
          <div className="mb-8 sm:mb-10 text-center">
            <div className="text-caption-up uppercase text-primary">{t("constellation.kicker")}</div>
            <h2 className="mt-2 text-display-sm sm:text-display-md text-ink">{t("constellation.title", { n: snap.slots.length })}</h2>
            <p className="mx-auto mt-3 max-w-xl text-body-md text-slate">
              {t("constellation.intro")}
            </p>
          </div>
          <Constellation
            slots={snap.slots}
            hints={snap.hints}
            totalChecked={snap.totals.total_checked}
            totalLocations={snap.totals.total_locations}
          />
        </section>
      )}

      <section className="mx-auto max-w-[1200px] px-4 sm:px-6 py-12 sm:py-section">
        <div className="mb-6 sm:mb-8 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-caption-up uppercase text-primary">{t("dash.kicker")}</div>
            <h2 className="mt-2 text-display-sm sm:text-display-md text-ink">{t("dash.title")}</h2>
          </div>
          <div className="text-body-sm text-steel">{t("dash.active_n", { n: snap.slots.length })}</div>
        </div>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {snap.slots.map((s) => (
            <SlotCard key={s.slot} slot={s} hintPointsEstimated={snap.hint_points_estimated} />
          ))}
        </div>
      </section>

      {config.features.death_leaderboard && deaths?.available && deaths.rows.length > 0 && (
        <section className="mx-auto max-w-[1200px] px-4 sm:px-6 pb-12 sm:pb-section">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="text-caption-up uppercase text-brand-orange">{t("deaths.kicker")}</div>
              <h2 className="mt-2 text-display-sm sm:text-display-md text-ink">{t("deaths.title")}</h2>
            </div>
            <div className="text-body-sm text-steel">
              {t("deaths.contenders", { n: deaths.rows.length, plural: deaths.rows.length === 1 ? "" : "s" })}
            </div>
          </div>
          <ol className="rounded-lg border hair bg-canvas divide-y hair-soft transition-colors duration-300">
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
