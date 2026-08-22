import { useT } from "../i18n";
import { useConfig, resolveAssetUrl } from "../config";
import { ServerStatus } from "../api";

type Props = {
  seed: string;
  totalChecked: number;
  totalLocations: number;
  slots: number;
  hints: number;
  hintsFound: number;
  latestHint: string | null;
  server: ServerStatus;
};

export default function Hero({ seed, totalChecked, totalLocations, slots, hints, hintsFound, latestHint, server }: Props) {
  const { t } = useT();
  const config = useConfig();
  const heroImage = config.branding.hero_image ? resolveAssetUrl(config.branding.hero_image) : "";
  const pct = totalLocations > 0 ? (100 * totalChecked) / totalLocations : 0;
  return (
    <section className="relative overflow-hidden bg-brand-navy text-onDark transition-colors duration-300">
      {/* Decorative hero image, pinned to the right edge, mirrored, with a left-side fade into the navy.
      hero_image_fade (0-1) controls how far that fade reaches into the image:
      0 = minimal, near the full image shows
      1 = a long, soft transition
      This is why this is a reach/width, not an opacity of the fade itself. */}
      {heroImage && (() => {
        const fade = Math.min(1, Math.max(0, config.branding.hero_image_fade));
        const reach = 15 + fade * 55;
        return (
          <img
            src={heroImage}
            alt=""
            aria-hidden
            className="pointer-events-none absolute inset-y-0 right-0 z-0 h-full select-none opacity-20 sm:opacity-40"
            style={{
              objectFit: "contain",
              objectPosition: "right center",
              transform: "scaleX(-1)",
              WebkitMaskImage: `linear-gradient(to left, transparent 0%, #000 ${reach}%)`,
              maskImage:       `linear-gradient(to left, transparent 0%, #000 ${reach}%)`,
            }}
          />
        );
      })()}
      <Decoration />
      <div className="relative z-10 mx-auto max-w-[1200px] px-4 sm:px-6 py-12 sm:py-20 lg:py-28">
        <div className="text-caption-up uppercase text-brand-purple-300">{t("hero.kicker")}</div>
        <h1 className="mt-4 text-display-md sm:text-display-xl lg:text-display-mega text-onDark">{config.branding.hero_title || "Archipelago"}</h1>
        <p className="mt-5 max-w-xl text-body-md sm:text-subtitle text-onDarkMuted">{t("hero.intro")}</p>

        <div className="mt-8 sm:mt-12 rounded-lg border hair bg-canvas p-4 sm:p-6 shadow-mockup">
          <div className="mb-4 flex items-center gap-1.5">
            <span className="dot bg-semantic-error/70" />
            <span className="dot bg-brand-yellow" />
            <span className="dot bg-semantic-success/70" />
            <span className="ml-2 font-mono text-code text-stone">archipelago / dashboard</span>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Pane label={t("hero.pane.world")} tint="lavender">
              <Line label={t("hero.field.seed")} value={seed || "—"} />
              <Line label={t("hero.field.slots")} value={String(slots)} />
            </Pane>
            <Pane label={t("hero.pane.checks")} tint="mint">
              <Line label={t("hero.field.progress")} value={`${pct.toFixed(1)}%`} />
              <Line label={t("hero.field.checked_total")} value={`${totalChecked} / ${totalLocations}`} />
            </Pane>
            <Pane label={t("hero.pane.hints")} tint="peach">
              <Line label={t("hero.field.open")} value={String(hints)} />
              <Line label={t("hero.field.found")} value={String(hintsFound)} />
              <Line label={t("hero.field.latest")} value={latestHint ?? "—"} />
            </Pane>
            <Pane label={t("hero.pane.server")} tint="sky">
              <div className={`text-body-sm font-medium ${server.connected ? "text-semantic-success" : "text-semantic-error"}`}>
                {t(server.connected ? "hero.field.running" : "hero.field.unreachable")}
              </div>
              <div className="text-body-sm text-tintInk">{t("hero.field.address", { host: server.host, port: server.port })}</div>
              <div className="text-body-sm text-tintInkSoft">{t("hero.field.tracker")}</div>
            </Pane>
          </div>
        </div>
      </div>
    </section>
  );
}

function Pane({ label, tint, children }: { label: string; tint: "peach" | "rose" | "mint" | "lavender" | "sky" | "yellow"; children: React.ReactNode }) {
  const bg = {
    peach: "bg-card-peach",
    rose: "bg-card-rose",
    mint: "bg-card-mint",
    lavender: "bg-card-lavender",
    sky: "bg-card-sky",
    yellow: "bg-card-yellow",
  }[tint];
  return (
    <div className={`rounded-lg ${bg} p-5`}>
      <div className="text-caption-up uppercase text-tintInk/60">{label}</div>
      <div className="mt-3 space-y-1">{children}</div>
    </div>
  );
}

function Line({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className={`${mono ? "font-mono text-code" : "text-body-sm"} text-tintInkSoft`}>{label}</span>
      <span className={`${mono ? "font-mono text-code" : "text-body-sm font-medium"} text-tintInk tabular-nums`}>{value}</span>
    </div>
  );
}

function Decoration() {
  // Sticky-note dots scattered around the headline.
  const dots: { left: string; top: string; cls: string; size: number }[] = [
    { left: "8%",  top: "20%", cls: "bg-brand-purple", size: 12 },
    { left: "82%", top: "18%", cls: "bg-brand-pink",   size: 10 },
    { left: "92%", top: "70%", cls: "bg-brand-orange", size: 14 },
    { left: "12%", top: "75%", cls: "bg-brand-teal",   size: 10 },
    { left: "70%", top: "85%", cls: "bg-brand-yellow", size: 12 },
    { left: "30%", top: "12%", cls: "bg-brand-green",  size: 8 },
  ];
  return (
    <div aria-hidden className="absolute inset-0 pointer-events-none">
      {dots.map((d, i) => (
        <span
          key={i}
          className={`absolute rounded-pill ${d.cls} opacity-90`}
          style={{ left: d.left, top: d.top, width: d.size, height: d.size }}
        />
      ))}
    </div>
  );
}
