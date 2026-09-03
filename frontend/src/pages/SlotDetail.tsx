import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { SlotDetail as SlotDetailT, api, liveSocket } from "../api";
import ProgressBar from "../components/ProgressBar";
import BadgePill from "../components/BadgePill";
import GameIcon from "../components/GameIcon";
import LoadingScreen, { markConnected } from "../components/LoadingScreen";
import { useT } from "../i18n";

type Filter = "all" | "remaining" | "checked" | "hinted" | "received";

export default function SlotDetail() {
  const { name = "" } = useParams();
  const { t, lang } = useT();
  const [data, setData] = useState<SlotDetailT | null>(null);
  const [filter, setFilter] = useState<Filter>("remaining");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.slot(name).then(setData).catch(console.error);
    return liveSocket(() => {
      api.slot(name).then(setData).catch(() => {});
    });
  }, [name]);

  useEffect(() => {
    if (data) markConnected();
  }, [data]);

  const hintedLocIds = useMemo(
    () => new Set((data?.hints || []).filter((h) => h.finding_slot === data?.slot.slot).map((h) => h.location_id)),
    [data],
  );

  const visible = useMemo(() => {
    if (!data) return [];
    return data.locations.filter((l) => {
      if (filter === "remaining" && l.checked) return false;
      if (filter === "checked" && !l.checked) return false;
      if (filter === "hinted" && !hintedLocIds.has(l.id)) return false;
      if (search && !l.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [data, filter, search, hintedLocIds]);

  const visibleReceived = useMemo(() => {
    if (!data) return [];
    const q = search.toLowerCase();
    return data.received_items.filter(
      (r) =>
        !q ||
        r.item_name.toLowerCase().includes(q) ||
        r.sender.toLowerCase().includes(q) ||
        r.location_name.toLowerCase().includes(q),
    );
  }, [data, search]);

  const counts = useMemo(() => {
    if (!data) return { all: 0, remaining: 0, checked: 0, hinted: 0, received: 0 };
    const checked = data.locations.filter((l) => l.checked).length;
    return {
      all: data.locations.length,
      remaining: data.locations.length - checked,
      checked,
      hinted: data.locations.filter((l) => hintedLocIds.has(l.id)).length,
      received: data.received_items.length,
    };
  }, [data, hintedLocIds]);

  if (!data) {
    return <LoadingScreen />;
  }

  const s = data.slot;

  return (
    <div className="mx-auto max-w-[1200px] px-4 sm:px-6 py-12">
      <Link to="/" className="text-body-sm text-steel hover:text-ink">{t("slot.back")}</Link>

      <header className="mt-4 flex flex-wrap items-end gap-6 border-b hair pb-8">
        <div>
          <div className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 rounded-pill ${s.online ? "bg-semantic-success" : "bg-stone"}`} />
            <h1 className="text-display-sm sm:text-display-md text-ink break-words">{s.name}</h1>
            {s.goal_completed && <BadgePill tone="success">{t("slot.goal")}</BadgePill>}
          </div>
          <div className="mt-1 flex items-center gap-2 font-mono text-body-sm text-slate">
            <GameIcon game={s.game} size={18} />
            <span>{s.game}</span>
          </div>
        </div>
        <div className="ml-auto flex flex-col items-stretch gap-3">
          <div className="flex flex-wrap items-end gap-x-8 gap-y-3 text-body-sm">
            <Stat label={t("slot.progress")} value={`${s.percent.toFixed(1)}%`} />
            <Stat label={t("slot.checks")} value={`${s.checked} / ${s.total}`} />
            <Stat label={t("slot.remaining")} value={String(s.remaining)} />
            <Stat
              label={t("slot.hint_pts")}
              value={String(s.hint_points)}
              title={data.hint_points_estimated ? t("slot.hint_pts_estimated_note") : undefined}
              suffix={data.hint_points_estimated ? "*" : undefined}
            />
            <Stat label={t("slot.open_hints")} value={String(s.open_hints)} />
          </div>
          <ProgressBar value={s.checked} total={s.total} />
        </div>
      </header>

      <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-[1fr,320px]">
        <section>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Tab active={filter === "all"} onClick={() => setFilter("all")}>{t("slot.tab.all")}</Tab>
            <Tab active={filter === "remaining"} onClick={() => setFilter("remaining")}>{t("slot.tab.remaining")}</Tab>
            <Tab active={filter === "checked"} onClick={() => setFilter("checked")}>{t("slot.tab.checked")}</Tab>
            <Tab active={filter === "hinted"} onClick={() => setFilter("hinted")}>{t("slot.tab.hinted")}</Tab>
            <Tab active={filter === "received"} onClick={() => setFilter("received")}>{t("slot.tab.received")}</Tab>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={filter === "received" ? t("slot.search_received") : t("slot.search_locations")}
              className="w-full sm:ml-auto sm:w-auto h-10 rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
            />
          </div>

          <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1 text-caption text-steel tabular-nums">
            <span className={filter === "all" ? "text-ink font-medium" : ""}>{t("slot.tab.all")} {counts.all}</span>
            <span aria-hidden>·</span>
            <span className={filter === "remaining" ? "text-ink font-medium" : ""}>{t("slot.tab.remaining")} {counts.remaining}</span>
            <span aria-hidden>·</span>
            <span className={filter === "checked" ? "text-ink font-medium" : ""}>{t("slot.tab.checked")} {counts.checked}</span>
            <span aria-hidden>·</span>
            <span className={filter === "hinted" ? "text-ink font-medium" : ""}>{t("slot.tab.hinted")} {counts.hinted}</span>
            <span aria-hidden>·</span>
            <span className={filter === "received" ? "text-ink font-medium" : ""}>{t("slot.tab.received")} {counts.received}</span>
          </div>

          {filter === "received" ? (
            <ul className="divide-y hair-soft rounded-lg border hair bg-canvas">
              {visibleReceived.map((r, i) => (
                <li key={i} className="px-4 py-3">
                  <div className="flex items-baseline gap-3">
                    <span className="min-w-0 break-words text-body-sm text-ink font-medium">{r.item_name}</span>
                    <span className="ml-auto shrink-0 text-caption text-steel tabular-nums">
                      {r.timestamp != null ? formatWhen(r.timestamp, lang) : t("slot.received.undated")}
                    </span>
                  </div>
                  <div className="mt-0.5 font-mono text-caption text-slate break-words">
                    {t("slot.received.from", { sender: r.sender, loc: r.location_name })}
                  </div>
                </li>
              ))}
              {visibleReceived.length === 0 && (
                <li className="px-4 py-8 text-center text-body-sm text-stone">{t("slot.received_panel.empty")}</li>
              )}
            </ul>
          ) : (
            <ul className="divide-y hair-soft rounded-lg border hair bg-canvas">
              {visible.map((l) => (
                <li key={l.id} className="flex items-center gap-3 px-4 py-3">
                  <span
                    className={`h-1.5 w-1.5 rounded-pill ${l.checked ? "bg-semantic-success" : hintedLocIds.has(l.id) ? "bg-primary" : "bg-stone"}`}
                  />
                  <span className={`text-body-sm ${l.checked ? "text-stone line-through" : "text-ink"}`}>
                    {l.name}
                  </span>
                  {l.item_name && (
                    <span className="ml-auto font-mono text-caption text-slate">{l.item_name}</span>
                  )}
                </li>
              ))}
              {visible.length === 0 && (
                <li className="px-4 py-8 text-center text-body-sm text-stone">{t("slot.no_locations")}</li>
              )}
            </ul>
          )}
        </section>

        <aside className="rounded-lg border hair bg-canvas p-5">
          <h3 className="text-title-md text-ink">{t("slot.hints_panel.title")}</h3>
          <p className="mt-1 text-body-sm text-steel">{t("slot.hints_panel.sub")}</p>
          <ul className="mt-4 space-y-3">
            {data.hints.map((h, i) => (
              <li key={i} className="rounded-md bg-surface p-3">
                <div className="text-caption text-steel">
                  {h.finding_slot === s.slot ? t("slot.hint.you_find") : t("slot.hint.you_receive")}
                </div>
                <div className="text-body-sm text-ink font-medium">{h.item_name}</div>
                <div className="font-mono text-caption text-slate">{h.location_name}</div>
                <div className="mt-2">
                  <BadgePill tone={h.found ? "success" : "primary"}>
                    {h.found ? t("slot.status.found") : t("slot.status.open")}
                  </BadgePill>
                </div>
              </li>
            ))}
            {data.hints.length === 0 && (
              <li className="text-body-sm text-stone">{t("slot.hints_panel.empty")}</li>
            )}
          </ul>
        </aside>
      </div>
    </div>
  );
}

function formatWhen(epochSeconds: number, lang: string): string {
  return new Date(epochSeconds * 1000).toLocaleString(lang === "fr" ? "fr-FR" : "en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Stat({ label, value, title, suffix }: { label: string; value: string; title?: string; suffix?: string }) {
  return (
    <div title={title}>
      <div className="text-caption text-steel uppercase tracking-[0.06em]">{label}</div>
      <div className="text-title-sm text-ink tabular-nums">
        {value}
        {suffix && <span className="ml-0.5 text-steel">{suffix}</span>}
      </div>
    </div>
  );
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`h-9 rounded-pill border px-4 text-body-sm font-medium transition-colors ${
        active ? "bg-primary text-white border-primary" : "border-hairline text-ink hover:bg-surface"
      }`}
    >
      {children}
    </button>
  );
}
