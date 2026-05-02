import { ReactNode } from "react";

type Tone = "default" | "success" | "muted" | "primary";

const tones: Record<Tone, string> = {
  default: "bg-surface-cardElevated text-bodyStrong",
  success: "bg-semantic-success/15 text-semantic-success",
  muted: "bg-surface-card text-mutedSoft",
  primary: "bg-primary/20 text-primary-glow",
};

export default function BadgePill({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-pill px-2.5 py-[3px] text-caption-up uppercase tracking-[0.08em] ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
