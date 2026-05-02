import { Link } from "react-router-dom";
import { Slot } from "../api";
import ProgressBar from "./ProgressBar";
import BadgePill from "./BadgePill";

export default function SlotCard({ slot }: { slot: Slot }) {
  return (
    <Link
      to={`/slot/${encodeURIComponent(slot.name)}`}
      className="group block rounded-xl border hair bg-surface-card p-5 transition-colors hover:border-hairline-strong"
    >
      <div className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-pill ${slot.online ? "bg-semantic-success shadow-[0_0_8px_#33d17a]" : "bg-mutedSoft"}`}
          aria-label={slot.online ? "online" : "offline"}
        />
        <span className="text-title-sm text-bodyStrong truncate">{slot.name}</span>
        {slot.goal_completed && (
          <span className="ml-auto"><BadgePill tone="success">Goal</BadgePill></span>
        )}
      </div>
      <div className="mt-1 text-body-sm text-body truncate font-mono">{slot.game}</div>

      <div className="mt-5 flex items-baseline gap-2">
        <span className="text-display-md text-bodyStrong tabular-nums">
          {slot.percent.toFixed(0)}
        </span>
        <span className="text-body-sm text-mutedSoft">%</span>
        <span className="ml-auto text-body-sm text-body tabular-nums">
          {slot.checked}<span className="text-mutedSoft"> / {slot.total}</span>
        </span>
      </div>
      <div className="mt-2"><ProgressBar value={slot.checked} total={slot.total} /></div>

      <div className="mt-4 flex items-center justify-between text-caption text-body">
        <span><span className="text-mutedSoft">remaining </span>{slot.remaining}</span>
        <span><span className="text-mutedSoft">hint pts </span>{slot.hint_points}</span>
        <span><span className="text-mutedSoft">hints </span>{slot.open_hints}</span>
      </div>
    </Link>
  );
}
