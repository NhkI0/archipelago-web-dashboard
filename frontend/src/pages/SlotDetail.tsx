import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { SlotDetail as SlotDetailT, api, liveSocket } from "../api";
import ProgressBar from "../components/ProgressBar";
import BadgePill from "../components/BadgePill";
import GameIcon from "../components/GameIcon";
import { useT } from "../i18n";

type Filter = "all" | "remaining" | "checked" | "hinted";

export default function SlotDetail() {
  const { name = "" } = useParams();
  const { t } = useT();
  const [data, setData] = useState<SlotDetailT | null>(null);
  const [filter, setFilter] = useState<Filter>("remaining");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.slot(name).then(setData).catch(console.error);
    return liveSocket(() => {
      api.slot(name).then(setData).catch(() => {});
    });
  }, [name]);

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

  if (!data) {
    return <div className="mx-auto max-w-[1200px] px-6 py-12 text-slate">{t("common.loading")}</div>;
  }

  const s = data.slot;

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-12">
      <Link to="/" className="text-body-sm text-steel hover:text-ink">{t("slot.back")}</Link>

      <header className="mt-4 flex flex-wrap items-end gap-6 border-b hair pb-8">
        <div>
          <div className="flex items-center gap-3">
            <span className={`h-2.5 w-2.5 rounded-pill ${s.online ? "bg-semantic-success" : "bg-stone"}`} />
            <h1 className="text-display-md text-ink">{s.name}</h1>
            {s.goal_completed && <BadgePill tone="success">{t("slot.goal")}</BadgePill>}
          </div>
          <div className="mt-1 flex items-center gap-2 font-mono text-body-sm text-slate">
            <GameIcon game={s.game} size={18} />
            <span>{s.game}</span>
          </div>
        </div>
        <div className="ml-auto flex flex-wrap items-end gap-x-8 gap-y-3 text-body-sm">
          <Stat label={t("slot.progress")} value={`${s.percent.toFixed(1)}%`} />
          <Stat label={t("slot.checks")} value={`${s.checked} / ${s.total}`} />
          <Stat label={t("slot.remaining")} value={String(s.remaining)} />
          <Stat label={t("slot.hint_pts")} value={String(s.hint_points)} />
          <Stat label={t("slot.open_hints")} value={String(s.open_hints)} />
        </div>
      </header>

      <div className="mt-6 max-w-md"><ProgressBar value={s.checked} total={s.total} /></div>

      <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-[1fr,320px]">
        <section>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <Tab active={filter === "all"} onClick={() => setFilter("all")}>{t("slot.tab.all")}</Tab>
            <Tab active={filter === "remaining"} onClick={() => setFilter("remaining")}>{t("slot.tab.remaining")}</Tab>
            <Tab active={filter === "checked"} onClick={() => setFilter("checked")}>{t("slot.tab.checked")}</Tab>
            <Tab active={filter === "hinted"} onClick={() => setFilter("hinted")}>{t("slot.tab.hinted")}</Tab>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("slot.search_locations")}
              className="ml-auto h-10 rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
            />
          </div>

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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-caption text-steel uppercase tracking-[0.06em]">{label}</div>
      <div className="text-title-sm text-ink tabular-nums">{value}</div>
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
