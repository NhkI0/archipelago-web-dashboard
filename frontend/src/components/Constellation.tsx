import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Hint, Slot } from "../api";
import { useT } from "../i18n";
import GameIcon from "./GameIcon";

const TINTS = [
  "bg-card-peach",
  "bg-card-rose",
  "bg-card-mint",
  "bg-card-lavender",
  "bg-card-sky",
  "bg-card-yellow",
  "bg-card-cream",
];

const VB = 600;        // SVG viewBox
const CX = VB / 2;
const CY = VB / 2;
const R  = 230;        // ring radius (in SVG units)

type Props = {
  slots: Slot[];
  hints: Hint[];
  totalChecked: number;
  totalLocations: number;
};

function nodePos(i: number, n: number) {
  const angle = (-Math.PI / 2) + (i * 2 * Math.PI / n);
  return { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle), angle };
}

export default function Constellation({ slots, hints, totalChecked, totalLocations }: Props) {
  const { t } = useT();
  const [hover, setHover] = useState<number | null>(null);

  const pcts = useMemo(() => slots.map((_, i) => nodePos(i, slots.length)), [slots.length]);
  const slotIndex = useMemo(() => new Map(slots.map((s, i) => [s.slot, i])), [slots]);

  // Pre-shuffle so arcs through the centre don't overlap perfectly.
  const arcs = useMemo(() => {
    return hints
      .map((h, idx) => {
        const fi = slotIndex.get(h.finding_slot);
        const ri = slotIndex.get(h.receiving_slot);
        if (fi == null || ri == null) return null;
        const a = pcts[fi];
        const b = pcts[ri];
        if (!a || !b) return null;
        const mx = CX + (idx % 2 === 0 ? 22 : -22);
        const my = CY + (idx % 3 === 0 ? -28 : 16);
        return { h, a, b, mx, my, key: idx };
      })
      .filter((x): x is NonNullable<typeof x> => x != null);
  }, [hints, slotIndex, pcts]);

  const totalPct = totalLocations > 0 ? (100 * totalChecked) / totalLocations : 0;

  function isInvolved(slotId: number, h: Hint) {
    return h.finding_slot === slotId || h.receiving_slot === slotId;
  }

  const hoveredSlot = hover != null ? slots.find(s => s.slot === hover) : null;
  const hoveredIncoming = hoveredSlot ? hints.filter(h => h.receiving_slot === hoveredSlot.slot) : [];
  const hoveredOutgoing = hoveredSlot ? hints.filter(h => h.finding_slot === hoveredSlot.slot)  : [];

  return (
    <section className="relative">
      <div className="constellation relative mx-auto aspect-square max-w-[640px]">
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox={`0 0 ${VB} ${VB}`}
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Soft guide ring */}
          <circle cx={CX} cy={CY} r={R} fill="none" stroke="#ede9e4" strokeDasharray="4 6" />
          {arcs.map(({ h, a, b, mx, my, key }) => {
            const involved = hover === null || isInvolved(hover, h);
            const fresh = !h.found;
            return (
              <path
                key={key}
                d={`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`}
                fill="none"
                stroke={fresh ? "#5645d4" : "#d6b6f6"}
                strokeWidth={fresh ? 2.5 : 1.5}
                strokeLinecap="round"
                strokeDasharray={fresh ? "6 4" : undefined}
                style={{
                  opacity: involved ? (fresh ? 0.95 : 0.5) : 0.06,
                  transition: "opacity 200ms ease",
                  animation: fresh ? "ap-dash 1.6s linear infinite" : undefined,
                }}
              />
            );
          })}
        </svg>

        {/* Centre medallion */}
        <div className="absolute left-1/2 top-1/2 z-10 w-56 -translate-x-1/2 -translate-y-1/2 rounded-2xl border hair bg-canvas p-5 text-center shadow-mockup">
          <div className="text-caption-up uppercase text-primary">{t("dash.kicker")}</div>
          <div className="mt-1 text-display-sm text-ink tabular-nums tracking-tight">{totalPct.toFixed(1)}%</div>
          <div className="mt-1 font-mono text-caption text-steel tabular-nums">
            {totalChecked.toLocaleString()} / {totalLocations.toLocaleString()}
          </div>
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-pill bg-hairline">
            <div className="h-full rounded-pill bg-primary" style={{ width: `${totalPct}%` }} />
          </div>
        </div>

        {/* Slot avatars */}
        {slots.map((s, i) => {
          const p = pcts[i];
          const x = (p.x / VB) * 100;
          const y = (p.y / VB) * 100;
          const tint = TINTS[s.slot % TINTS.length];
          const dimmed = hover !== null && hover !== s.slot && !hints.some(h => isInvolved(s.slot, h) && (h.finding_slot === hover || h.receiving_slot === hover));
          return (
            <Link
              key={s.slot}
              to={`/slot/${encodeURIComponent(s.name)}`}
              onMouseEnter={() => setHover(s.slot)}
              onMouseLeave={() => setHover(null)}
              className="absolute z-20 -translate-x-1/2 -translate-y-1/2 text-center"
              style={{
                left: `${x}%`,
                top: `${y}%`,
                width: 148,
                opacity: dimmed ? 0.35 : 1,
                transition: "opacity 200ms ease, transform 200ms ease",
              }}
            >
              <div className={`relative mx-auto inline-flex h-[72px] w-[72px] items-center justify-center rounded-pill ${tint} border-4 border-canvas font-semibold text-charcoal shadow-mockup`}>
                <GameIcon game={s.game} size={36} />
                <span
                  className={`absolute -left-1 -top-1 h-3.5 w-3.5 rounded-pill border-[3px] border-canvas ${s.online ? "bg-semantic-success" : "bg-stone"}`}
                  aria-label={s.online ? t("slot.online") : t("slot.offline")}
                />
                <span className="absolute -bottom-2 -right-2 inline-flex h-6 items-center rounded-pill border-[3px] border-canvas bg-ink px-2 text-caption-up tabular-nums text-white">
                  {s.percent.toFixed(0)}%
                </span>
              </div>
              <div className="mt-3 text-body-sm font-medium text-ink truncate">{s.name}</div>
              <div className="font-mono text-caption text-steel truncate">{s.game}</div>
              {s.goal_completed && (
                <div className="mt-1 inline-block rounded-pill bg-semantic-success px-2 py-[1px] text-caption-up uppercase text-white">
                  {t("slot.goal")}
                </div>
              )}
            </Link>
          );
        })}
      </div>

      {/* Hover detail bar */}
      <div className="mx-auto mt-6 max-w-[760px] rounded-lg border hair bg-surface-soft px-5 py-3 text-body-sm text-slate">
        {hoveredSlot ? (
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-1">
            <Field label={t("nav.slot")} value={hoveredSlot.name} />
            <Field label="game" value={hoveredSlot.game} />
            <Field label={t("slot.progress")} value={`${hoveredSlot.percent.toFixed(1)}%`} />
            <Field label={t("hints.subtab.mine_in")} value={String(hoveredOutgoing.length)} />
            <Field label={t("hints.subtab.mine_for")} value={String(hoveredIncoming.length)} />
          </div>
        ) : (
          <div className="text-steel italic">
            Hover a player to highlight their hint threads · click to open the detail page.
          </div>
        )}
      </div>

      {/* Tiny SVG dash-loop keyframes — scoped to this component via a style tag */}
      <style>{`@keyframes ap-dash { to { stroke-dashoffset: -40; } }`}</style>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <span className="mr-2 text-caption-up uppercase text-steel">{label}</span>
      <span className="font-medium text-ink">{value}</span>
    </span>
  );
}
