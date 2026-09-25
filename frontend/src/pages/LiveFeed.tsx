import { useEffect, useState } from "react";
import { useT, Lang } from "../i18n";
import { colorForSlot } from "../playerColors";
import GameIcon from "../components/GameIcon";
import LoadingScreen, { markConnected } from "../components/LoadingScreen";
import { FeedItem, isFeedReady, subscribeFeed } from "../liveFeedStore";

type Tab = "all" | "check" | "hint" | "goal";

export default function LiveFeed() {
  const { t, lang } = useT();
  const [items, setItems] = useState<FeedItem[]>([]);
  const [tab, setTab] = useState<Tab>("all");
  const [ready, setReady] = useState(isFeedReady());

  // The socket subscription itself lives in LiveFeedCollector; this just reads its buffer.
  useEffect(() => subscribeFeed((its) => {
    setItems(its);
    setReady(isFeedReady());
  }), []);

  useEffect(() => {
    if (ready) markConnected();
  }, [ready]);

  if (!ready) return <LoadingScreen />;

  const visible = tab === "all" ? items : items.filter((i) => i.kind === tab);

  return (
    <div className="mx-auto max-w-[1200px] px-4 sm:px-6 py-12">
      <header className="border-b hair pb-8">
        <div className="text-caption-up uppercase text-primary">{t("live.kicker")}</div>
        <h1 className="mt-2 text-display-sm sm:text-display-md text-ink">{t("live.title")}</h1>
        <p className="mt-2 text-body-sm text-slate">{t("live.intro")}</p>
      </header>

      <div className="mt-8 flex flex-wrap gap-3">
        <PillTab active={tab === "all"} onClick={() => setTab("all")}>{t("live.tab.all")}</PillTab>
        <PillTab active={tab === "check"} onClick={() => setTab("check")}>{t("live.tab.checks")}</PillTab>
        <PillTab active={tab === "hint"} onClick={() => setTab("hint")}>{t("live.tab.hints")}</PillTab>
        <PillTab active={tab === "goal"} onClick={() => setTab("goal")}>{t("live.tab.goals")}</PillTab>
      </div>

      <div className="mt-6 rounded-lg border hair bg-canvas transition-colors duration-300">
        <ul className="divide-y hair-soft">
          {visible.map((it) => (
            <FeedRow key={it.id} item={it} lang={lang} t={t} />
          ))}
          {visible.length === 0 && (
            <li className="px-4 py-12 text-center text-body-sm text-stone">{t("live.empty")}</li>
          )}
        </ul>
      </div>
    </div>
  );
}

function FeedRow({ item, lang, t }: { item: FeedItem; lang: Lang; t: (k: string, v?: Record<string, string | number>) => string }) {
  const when = formatWhen(item.ts, lang);
  if (item.kind === "check") {
    return (
      <li className="flex flex-wrap items-center gap-2 px-4 py-3 text-body-sm">
        <GameIcon game={item.finderGame} size={18} />
        <span className={`font-medium ${colorForSlot(item.finder)}`}>{item.finder}</span>
        <span className="text-steel">{t("live.row.found")}</span>
        <span className="text-ink font-medium">{item.item}</span>
        <LocationChip name={item.location} />
        {item.recv !== item.finder && (
          <>
            <span className="text-steel">{t("live.row.for")}</span>
            <GameIcon game={item.recvGame} size={18} />
            <span className={`font-medium ${colorForSlot(item.recv)}`}>{item.recv}</span>
          </>
        )}
        <span className="ml-auto shrink-0 text-caption text-steel tabular-nums">{when}</span>
      </li>
    );
  }
  if (item.kind === "hint") {
    return (
      <li className="flex flex-wrap items-center gap-2 px-4 py-3 text-body-sm">
        <span className="inline-flex h-5 items-center rounded-pill bg-card-gray px-2 text-caption-up uppercase text-steel">
          {t("live.tab.hints")}
        </span>
        <span className="text-ink font-medium">{item.item}</span>
        <span className="text-steel">{t("live.row.hint_for")}</span>
        <span className={`font-medium ${colorForSlot(item.recv)}`}>{item.recv}</span>
        <span className="text-steel">{t("live.row.in")}</span>
        <span className={`font-medium ${colorForSlot(item.finder)}`}>{item.finder}</span>
        <LocationChip name={item.location} />
        <span className="ml-auto shrink-0 text-caption text-steel tabular-nums">{when}</span>
      </li>
    );
  }
  return (
    <li className="flex flex-wrap items-center gap-2 px-4 py-3 text-body-sm">
      <span className="inline-flex h-5 items-center rounded-pill bg-card-mint px-2 text-caption-up uppercase text-brand-green">
        {t("live.tab.goals")}
      </span>
      {item.game && <GameIcon game={item.game} size={18} />}
      <span className={`font-medium ${colorForSlot(item.name)}`}>{item.name}</span>
      <span className="text-steel">{t("live.row.goaled")}</span>
      <span className="ml-auto shrink-0 text-caption text-steel tabular-nums">{when}</span>
    </li>
  );
}

function LocationChip({ name }: { name: string }) {
  return (
    <span className="inline-flex max-w-full items-center truncate rounded-md bg-surface px-2 py-0.5 font-mono text-caption text-slate">
      {name}
    </span>
  );
}

function formatWhen(epochSeconds: number, lang: string): string {
  return new Date(epochSeconds * 1000).toLocaleTimeString(lang === "fr" ? "fr-FR" : "en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function PillTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`h-10 rounded-pill border px-5 text-body-sm font-medium transition-colors ${
        active ? "bg-primary text-white border-primary" : "border-hairline text-ink hover:bg-surface"
      }`}
    >
      {children}
    </button>
  );
}
