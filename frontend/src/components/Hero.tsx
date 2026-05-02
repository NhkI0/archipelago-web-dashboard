type Props = {
  seed: string;
  totalChecked: number;
  totalLocations: number;
  slots: number;
  hints: number;
};

export default function Hero({ seed, totalChecked, totalLocations, slots, hints }: Props) {
  const pct = totalLocations > 0 ? (100 * totalChecked) / totalLocations : 0;
  return (
    <section className="relative overflow-hidden border-b hair bg-canvas">
      <div className="spotlight-glow" aria-hidden />
      <div className="relative mx-auto max-w-[1200px] px-6 py-section">
        <div className="text-caption-up uppercase text-primary-glow">Multiworld</div>
        <h1 className="mt-4 text-display-xl text-bodyStrong">
          {seed || "—"}
        </h1>
        <p className="mt-4 max-w-xl text-body-md text-body">
          Live progression for every slot in this world. Sign in as your slot to spend hint
          points without leaving the browser.
        </p>

        {/* 2×2 terminal-mockup grid — Composio brand signature */}
        <div className="mt-12 max-w-3xl rounded-xl bg-canvas-deep p-8">
          <div className="grid grid-cols-2 gap-4">
            <Pane label="world.summary">
              <Line c="text-body">seed</Line>
              <Line c="text-bodyStrong">{seed || "—"}</Line>
              <Line c="text-body">slots</Line>
              <Line c="text-bodyStrong">{slots}</Line>
            </Pane>
            <Pane label="checks.global">
              <Line c="text-body">progress</Line>
              <Line c="text-bodyStrong">{pct.toFixed(1)}%</Line>
              <Line c="text-body">checked / total</Line>
              <Line c="text-bodyStrong">{totalChecked} / {totalLocations}</Line>
            </Pane>
            <Pane label="hints.in_flight">
              <Line c="text-body">open</Line>
              <Line c="text-bodyStrong">{hints}</Line>
              <Line c="text-mutedSoft">$ hint &lt;item&gt;</Line>
              <Line c="text-mutedSoft">$ hint_location &lt;loc&gt;</Line>
            </Pane>
            <Pane label="server.status">
              <Line c="text-semantic-success">● running</Line>
              <Line c="text-body">port 38281</Line>
              <Line c="text-mutedSoft">tracker · live ws</Line>
              <Line c="text-mutedSoft">spec by composio</Line>
            </Pane>
          </div>
        </div>
      </div>
    </section>
  );
}

function Pane({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-surface-card p-5">
      <div className="mb-2 flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-pill bg-semantic-error/70" />
        <span className="h-2 w-2 rounded-pill bg-[#e8c547]/70" />
        <span className="h-2 w-2 rounded-pill bg-semantic-success/70" />
        <span className="ml-2 font-mono text-code text-mutedSoft">{label}</span>
      </div>
      <div className="space-y-1 font-mono text-code">{children}</div>
    </div>
  );
}

function Line({ c, children }: { c: string; children: React.ReactNode }) {
  return <div className={c}>{children}</div>;
}
