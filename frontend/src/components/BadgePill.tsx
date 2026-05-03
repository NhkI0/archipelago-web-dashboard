import { ReactNode } from "react";

type Tone = "default" | "success" | "muted" | "primary" | "purple" | "pink" | "orange";

const tones: Record<Tone, string> = {
  default: "bg-card-gray text-charcoal",
  success: "bg-card-mint text-brand-green",
  muted: "bg-card-gray text-steel",
  primary: "bg-card-lavender text-brand-purple-800",
  purple: "bg-primary text-white",
  pink: "bg-brand-pink text-white",
  orange: "bg-brand-orange text-white",
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
      className={`inline-flex items-center rounded-pill px-2.5 py-[3px] text-caption-up uppercase ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
