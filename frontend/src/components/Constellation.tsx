import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Hint, Slot } from "../api";
import { useT } from "../i18n";
import { useTheme } from "../theme";
import GameIcon from "./GameIcon";
import MarqueeText from "./MarqueeText";

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
  const { theme } = useTheme();
  const [hover, setHover] = useState<number | null>(null);
  // Blend the faint "found" arcs into the canvas: darken on light, lighten on dark.
  const foundBlend = theme === "dark" ? ("screen" as const) : ("multiply" as const);

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
        if (fi === ri) {
          const ox = Math.cos(a.angle), oy = Math.sin(a.angle);
          // Full circle whose edge passes through the avatar centre (OFFSET = CIRCLE_R).
          // Outer extent from constellation centre = R + 2*CIRCLE_R, must stay <= VB/2 - MARGIN.
          // Tilt-scale: bigger when pointing up, smaller when pointing down (labels sit below).
          const MARGIN = 6;
          const BASE_R = Math.max(0, (VB / 2 - MARGIN - R) / 2.4); // ~27 with current R
          const tilt = 1 - 0.22 * oy; // oy = -1 (top) -> 1.22, oy = +1 (bottom) -> 0.78
          const CIRCLE_R = BASE_R * tilt;
          const OFFSET   = CIRCLE_R;
          const cxSelf = a.x + ox * OFFSET;
          const cySelf = a.y + oy * OFFSET;
          return {
            h, self: true as const, a, b, mx: 0, my: 0,
            sx: 0, sy: 0, ex: 0, ey: 0, cp1x: 0, cp1y: 0, cp2x: 0, cp2y: 0,
            cxSelf, cySelf, rSelf: CIRCLE_R, key: idx,
          };
        }
        // Curve perpendicular to the chord; vary side & magnitude per index so arcs fan out.
        const midX = (a.x + b.x) / 2;
        const midY = (a.y + b.y) / 2;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const len = Math.hypot(dx, dy) || 1;
        // Unit perpendicular (rotate chord 90°).
        const px = -dy / len;
        const py = dx / len;
        // Side alternates; magnitude scales with chord length and varies by index.
        const side = idx % 2 === 0 ? 1 : -1;
        const bend = (0.18 + ((idx * 37) % 23) / 110) * len * side;
        const mx = midX + px * bend;
        const my = midY + py * bend;
        return {
          h, self: false as const, a, b, mx, my,
          sx: 0, sy: 0, ex: 0, ey: 0, cp1x: 0, cp1y: 0, cp2x: 0, cp2y: 0,
          cxSelf: 0, cySelf: 0, rSelf: 0, key: idx,
        };
      })
      .filter((x): x is NonNullable<typeof x> => x != null);
  }, [hints, slotIndex, pcts]);
  
  const MAX_ANIMATED_ARCS = 120;
  const freshArcCount = useMemo(() => arcs.reduce((n, a) => n + (a.h.found ? 0 : 1), 0), [arcs]);
  const animateArcs = freshArcCount <= MAX_ANIMATED_ARCS;

  const totalPct = totalLocations > 0 ? (100 * totalChecked) / totalLocations : 0;

  function isInvolved(slotId: number, h: Hint) {
    return h.finding_slot === slotId || h.receiving_slot === slotId;
  }
  
  const relatedToHover = useMemo(() => {
    if (hover == null) return null;
    const set = new Set<number>();
    for (const h of hints) {
      if (h.finding_slot === hover) set.add(h.receiving_slot);
      if (h.receiving_slot === hover) set.add(h.finding_slot);
    }
    return set;
  }, [hover, hints]);

  // Grow the canvas with the slot count so avatars (fixed pixel size) keep
  // breathing room around the ring instead of crowding at the top.
  // ~62px of width per node keeps labels legible; clamp to a sane range.
  const maxWidth = Math.min(1100, Math.max(640, Math.round(slots.length * 62)));

  // Avatars, labels and radial gaps are sized in fixed pixels, while arcs and
  // node positions are relative to the canvas. To keep those proportions intact
  // on narrow screens (where the canvas is far smaller than its design size) we
  // render at the full design size and uniformly scale the whole thing down to
  // the available width. scale === 1 on wide viewports; < 1 on phones/tablets.
  const wrapRef = useRef<HTMLDivElement>(null);
  const [wrapW, setWrapW] = useState(maxWidth);
  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    setWrapW(el.clientWidth);
    const ro = new ResizeObserver(([e]) => setWrapW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const scale = Math.min(1, wrapW / maxWidth);

  const hoveredSlot = hover != null ? slots.find(s => s.slot === hover) : null;
  const hoveredIncoming = hoveredSlot ? hints.filter(h => h.receiving_slot === hoveredSlot.slot) : [];
  const hoveredOutgoing = hoveredSlot ? hints.filter(h => h.finding_slot === hoveredSlot.slot)  : [];

  return (
    <section className="relative">
      <div ref={wrapRef} className="relative mx-auto w-full" style={{ maxWidth, height: maxWidth * scale }}>
      <div
        className="constellation absolute left-0 top-0"
        style={{ width: maxWidth, height: maxWidth, transform: `scale(${scale})`, transformOrigin: "top left" }}
      >
        <svg
          className="absolute inset-0 h-full w-full"
          viewBox={`0 0 ${VB} ${VB}`}
          preserveAspectRatio="xMidYMid meet"
          overflow="visible"
        >
          {/* Soft guide ring */}
          <circle cx={CX} cy={CY} r={R} fill="none" style={{ stroke: "var(--c-arc-ring)", transition: "stroke 250ms ease" }} strokeDasharray="4 6" />
          {arcs.map(({ h, self, a, b, mx, my, cxSelf, cySelf, rSelf, key }) => {
            const involved = hover === null || isInvolved(hover, h);
            const fresh = !h.found;
            const commonStyle = {
              stroke: fresh ? "var(--c-arc-fresh)" : "var(--c-arc-found)",
              opacity: involved ? (fresh ? 0.95 : 0.35) : 0.05,
              mixBlendMode: fresh ? undefined : foundBlend,
              transition: "opacity 200ms ease, stroke 250ms ease",
              animation: fresh && animateArcs ? "ap-dash 1.6s linear infinite" : undefined,
            };
            if (self) {
              return (
                <circle
                  key={key}
                  cx={cxSelf}
                  cy={cySelf}
                  r={rSelf}
                  fill="none"
                  strokeWidth={fresh ? 2.5 : 1.25}
                  strokeDasharray={fresh ? "6 4" : undefined}
                  style={commonStyle}
                />
              );
            }
            return (
              <path
                key={key}
                d={`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`}
                fill="none"
                strokeWidth={fresh ? 2.5 : 1.25}
                strokeLinecap="round"
                strokeDasharray={fresh ? "6 4" : undefined}
                style={commonStyle}
              />
            );
          })}
        </svg>

        {/* Centre medallion */}
        <div className="absolute left-1/2 top-1/2 z-10 w-36 sm:w-56 -translate-x-1/2 -translate-y-1/2 rounded-2xl border hair bg-canvas p-3 sm:p-5 text-center shadow-mockup transition-colors duration-300">
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
          const dimmed = hover !== null && hover !== s.slot && !relatedToHover?.has(s.slot);
          // Float the label radially outward from the centre along the node's
          // angle, so it always sits on the outer edge clear of the arcs:
          // straight up at the top, up-right in the upper-right corner, etc.
          // The 50% terms shift the label by half its own size in the radial
          // direction (so its inner edge meets the node); GAP clears the avatar.
          const ox = Math.cos(p.angle);
          const oy = Math.sin(p.angle);
          const GAP = 46;
          const labelTransform =
            `translate(calc(-50% + ${(ox * 50).toFixed(2)}%), calc(-50% + ${(oy * 50).toFixed(2)}%))` +
            ` translate(${(ox * GAP).toFixed(1)}px, ${(oy * GAP).toFixed(1)}px)`;
          const label = (
            <div
              className="pointer-events-none absolute left-1/2 top-1/2 max-w-[88px] sm:max-w-[148px] rounded-lg bg-surface-soft px-2.5 py-1.5 text-center transition-colors duration-300"
              style={{ transform: labelTransform }}
            >
              <div className="text-body-sm font-medium text-ink truncate">{s.name}</div>
              <MarqueeText className="mt-0.5 font-mono text-caption text-slate">{s.game}</MarqueeText>
            </div>
          );
          return (
            <Link
              key={s.slot}
              to={`/slot/${encodeURIComponent(s.name)}`}
              onMouseEnter={() => setHover(s.slot)}
              onMouseLeave={() => setHover(null)}
              className="absolute z-20 w-12 sm:w-[72px] -translate-x-1/2 -translate-y-1/2 text-center"
              style={{
                left: `${x}%`,
                top: `${y}%`,
                opacity: dimmed ? 0.35 : 1,
                transition: "opacity 200ms ease, transform 200ms ease",
              }}
            >
              {label}
              <div className={`relative mx-auto inline-flex h-12 w-12 sm:h-[72px] sm:w-[72px] items-center justify-center rounded-pill ${tint} border-4 border-canvas font-semibold text-charcoal shadow-mockup transition-colors duration-300`}>
                <GameIcon game={s.game} size={24} />
                <span
                  className={`absolute -left-1 -top-1 h-3.5 w-3.5 rounded-pill border-[3px] border-canvas transition-colors duration-300 ${s.online ? "bg-semantic-success" : "bg-stone"}`}
                  aria-label={s.online ? t("slot.online") : t("slot.offline")}
                />
                <span
                  className={`absolute -bottom-2 -right-2 inline-flex h-6 items-center rounded-pill border-[3px] border-canvas px-2 text-caption-up uppercase tabular-nums transition-colors duration-300 ${s.goal_completed ? "bg-semantic-success text-white" : "bg-ink text-canvas"}`}
                >
                  {s.goal_completed ? t("slot.goal") : `${s.percent.toFixed(0)}%`}
                </span>
              </div>
            </Link>
          );
        })}
      </div>
      </div>

      {/* Hover detail bar */}
      <div className="mx-auto mt-6 max-w-[760px] rounded-lg border hair bg-surface-soft px-5 py-3 text-body-sm text-slate transition-colors duration-300">
        {hoveredSlot ? (
          <div className="flex flex-wrap items-baseline gap-x-8 gap-y-1">
            <Field label={t("nav.slot")} value={hoveredSlot.name} />
            <Field label={t("constellation.field.game")} value={hoveredSlot.game} />
            <Field label={t("slot.progress")} value={`${hoveredSlot.percent.toFixed(1)}%`} />
            <Field label={t("hints.subtab.mine_in")} value={String(hoveredOutgoing.length)} />
            <Field label={t("hints.subtab.mine_for")} value={String(hoveredIncoming.length)} />
          </div>
        ) : (
          <div className="text-steel italic">{t("constellation.hover_hint")}</div>
        )}
      </div>

      {/* Tiny SVG dash-loop keyframes, scoped to this component via a style tag */}
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
