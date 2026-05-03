import { Link } from "react-router-dom";
import { Slot } from "../api";
import ProgressBar from "./ProgressBar";
import BadgePill from "./BadgePill";
import { useT } from "../i18n";

const TINTS = [
  "bg-card-peach",
  "bg-card-rose",
  "bg-card-mint",
  "bg-card-lavender",
  "bg-card-sky",
  "bg-card-yellow",
  "bg-card-cream",
];

export default function SlotCard({ slot }: { slot: Slot }) {
  const { t } = useT();
  const tint = TINTS[slot.slot % TINTS.length];
  return (
    <Link
      to={`/slot/${encodeURIComponent(slot.name)}`}
      className="group block rounded-lg border hair bg-canvas p-6 transition-shadow hover:shadow-card"
    >
      <div className={`mb-4 inline-flex items-center gap-2 rounded-md ${tint} px-2.5 py-1`}>
        <span
          className={`h-1.5 w-1.5 rounded-pill ${slot.online ? "bg-semantic-success" : "bg-stone"}`}
          aria-label={slot.online ? t("slot.online") : t("slot.offline")}
        />
        <span className="font-mono text-caption text-charcoal truncate">{slot.game}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-title-sm text-ink truncate">{slot.name}</span>
        {slot.goal_completed && (
          <span className="ml-auto"><BadgePill tone="success">{t("slot.goal")}</BadgePill></span>
        )}
      </div>

      <div className="mt-5 flex items-baseline gap-2">
        <span className="text-display-md text-ink tabular-nums">{slot.percent.toFixed(0)}</span>
        <span className="text-body-sm text-stone">%</span>
        <span className="ml-auto text-body-sm text-slate tabular-nums">
          {slot.checked}<span className="text-stone"> / {slot.total}</span>
        </span>
      </div>
      <div className="mt-2"><ProgressBar value={slot.checked} total={slot.total} /></div>

      <div className="mt-4 flex items-center justify-between text-caption text-slate">
        <span><span className="text-stone">{t("slot.remaining")} </span>{slot.remaining}</span>
        <span><span className="text-stone">{t("slot.hint_pts")} </span>{slot.hint_points}</span>
        <span><span className="text-stone">{t("slot.hints")} </span>{slot.open_hints}</span>
      </div>
    </Link>
  );
}
