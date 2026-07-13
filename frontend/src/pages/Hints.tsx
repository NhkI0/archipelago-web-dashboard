import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Hint, HintTag, Me, SlotDetail, Snapshot, api, liveSocket } from "../api";
import LoadingScreen, { markConnected } from "../components/LoadingScreen";
import FlowerSpinner from "../components/FlowerSpinner";
import { useT } from "../i18n";

type Tab = "location" | "item" | "hints" | "received";
type HintFilter = "mine_for" | "mine_in" | "all";

export default function Hints() {
  const { t, lang } = useT();
  const [me, setMe] = useState<Me | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [detail, setDetail] = useState<SlotDetail | null>(null);
  const [tab, setTab] = useState<Tab>("item");
  const [hintFilter, setHintFilter] = useState<HintFilter>("mine_for");
  const [hideFound, setHideFound] = useState(false);
  const [sortByTag, setSortByTag] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ kind: "item" | "location"; target: string } | null>(null);

  useEffect(() => {
    api.me().then(setMe);
    api.state().then(setSnap);
    return liveSocket((e) => {
      if (e?.snapshot) setSnap(e.snapshot);
    });
  }, []);

  useEffect(() => {
    if (me?.logged_in) api.slot(me.slot).then(setDetail);
  }, [me]);

  useEffect(() => {
    if (me?.logged_in && snap) api.slot(me.slot).then(setDetail);
  }, [snap?.hints.length, me?.logged_in ? me.slot : null]);

  useEffect(() => {
    if (me && snap) markConnected();
  }, [me, snap]);

  const slotNames = useMemo(() => {
    const m = new Map<number, string>();
    if (snap) for (const s of snap.slots) m.set(s.slot, s.name);
    return m;
  }, [snap]);

  const allItems = useMemo(() => {
    if (!detail) return [] as { name: string; count: number }[];
    const hintedCounts = new Map<string, number>();
    for (const h of detail.hints) {
      if (h.receiving_slot === detail.slot.slot) {
        hintedCounts.set(h.item_name, (hintedCounts.get(h.item_name) ?? 0) + 1);
      }
    }
    const counts = new Map<string, number>();
    for (const name of detail.available_items) {
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    const result: { name: string; count: number }[] = [];
    for (const [name, count] of counts) {
      const remaining = count - (hintedCounts.get(name) ?? 0);
      if (remaining > 0) result.push({ name, count: remaining });
    }
    return result;
  }, [detail]);

  const remainingLocations = useMemo(() => {
    if (!detail) return [];
    const hinted = new Set(detail.hints.filter(h => h.finding_slot === detail.slot.slot).map(h => h.location_id));
    return detail.locations.filter(l => !l.checked && !hinted.has(l.id));
  }, [detail]);

  const visibleReceived = useMemo(() => {
    if (!detail) return [];
    const q = search.toLowerCase();
    return detail.received_items.filter(
      (r) =>
        !q ||
        r.item_name.toLowerCase().includes(q) ||
        r.sender.toLowerCase().includes(q) ||
        r.location_name.toLowerCase().includes(q),
    );
  }, [detail, search]);

  const visibleHints = useMemo(() => {
    if (!snap || !me || !me.logged_in) return [];
    const mySlot = detail?.slot.slot;
    let list: Hint[] = snap.hints;
    if (hintFilter === "mine_for") list = list.filter(h => h.receiving_slot === mySlot);
    else if (hintFilter === "mine_in") list = list.filter(h => h.finding_slot === mySlot);
    if (hideFound) list = list.filter(h => !h.found);
    const q = search.toLowerCase();
    if (q) list = list.filter(h =>
      h.item_name.toLowerCase().includes(q) ||
      h.location_name.toLowerCase().includes(q)
    );
    if (sortByTag) {
      // BKed → Mandatory → Comfort → untagged. Stable within each group, so
      // the server's existing order is preserved among same-tag hints.
      list = [...list].sort((a, b) => tagRank(a.tag) - tagRank(b.tag));
    }
    return list;
  }, [snap, me, detail, hintFilter, hideFound, search, sortByTag]);

  if (me === null || snap === null) {
    return <LoadingScreen />;
  }

  if (!me.logged_in) {
    return (
      <div className="mx-auto max-w-md px-6 py-section text-center">
        <h1 className="text-display-sm text-ink">{t("hints.signin_title")}</h1>
        <p className="mt-2 text-body-sm text-slate">{t("hints.signin_body")}</p>
        <Link
          to="/login"
          className="mt-6 inline-flex h-10 items-center rounded-md bg-primary px-5 text-btn text-white hover:bg-primary-active"
        >
          {t("nav.signin")}
        </Link>
      </div>
    );
  }

  function looksLikeFailure(reply: string | undefined): string | null {
    if (!reply) return null;
    const r = reply.toLowerCase();
    if (
      r.includes("not enough") ||
      r.includes("do not have") ||
      r.includes("cannot afford") ||
      r.includes("can't afford") ||
      r.includes("could not find") ||
      r.includes("ambiguous") ||
      r.includes("unknown") ||
      r.includes("no such") ||
      r.includes("already hinted")
    ) return reply;
    return null;
  }

  async function performSubmit(kind: "item" | "location", target: string) {
    setBusy(target);
    setError(null);
    try {
      const r = await api.hint(kind, target);
      const failure = r.error || looksLikeFailure(r.reply);
      if (failure) {
        setError(failure);
        return;
      }
      await Promise.all([
        api.me().then(setMe),
        api.state().then(setSnap),
      ]);
      if (me && me.logged_in) api.slot(me.slot).then(setDetail);
      setTab("hints");
      setSearch("");
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setBusy(null);
    }
  }

  function requestSubmit(kind: "item" | "location", target: string) {
    setError(null);
    setConfirm({ kind, target });
  }

  async function updateTag(h: Hint, tag: HintTag | "") {
    setError(null);
    try {
      await api.hintTag(h, tag);
      // The server also broadcasts the change over /ws/live, but refresh now
      // so the tag flips immediately for the person who set it.
      setSnap(await api.state());
    } catch (e: any) {
      setError(e.message || String(e));
    }
  }

  return (
    <div className="mx-auto max-w-[1200px] px-4 sm:px-6 py-12">
      <header className="flex flex-wrap items-end gap-6 border-b hair pb-8">
        <div>
          <div className="text-caption-up uppercase text-primary">{t("hints.kicker")}</div>
          <h1 className="mt-2 text-display-sm sm:text-display-md text-ink">{me.slot}</h1>
        </div>
        <div className="ml-auto flex flex-wrap items-end gap-x-8 gap-y-3 text-body-sm">
          <Stat label={t("slot.hint_pts")} value={String(me.hint_points)} />
          {detail && <Stat label={t("slot.checks")} value={`${detail.slot.checked} / ${detail.slot.total}`} />}
          {detail && <Stat label={t("slot.open_hints")} value={String(detail.slot.open_hints)} />}
        </div>
      </header>

      {(() => {
        const total = detail?.slot.total ?? 0;
        const pct = snap.hint_cost ?? 10;
        const cost = Math.ceil((pct / 100) * total);
        const affordable = cost > 0 ? Math.floor(me.hint_points / cost) : 0;
        return (
          <div className="mt-6 flex flex-wrap items-center gap-4 rounded-lg bg-surface px-5 py-4 transition-colors duration-300">
            <div className="flex items-center gap-2.5">
              <span className="h-2.5 w-2.5 rounded-pill bg-primary" />
              <span className="text-body-sm text-charcoal">
                {t("hints.banner.cost")} <span className="font-medium text-ink">{cost} pts</span>
                {" · "}{t("hints.banner.balance")} <span className="font-medium text-ink">{me.hint_points} pts</span>
              </span>
            </div>
            <div className="ml-auto text-body-sm text-slate">
              {t("hints.banner.afford", { n: affordable, plural: affordable === 1 ? "" : "s" })}
            </div>
          </div>
        );
      })()}

      <div className="mt-8 flex flex-wrap gap-3">
        <PillTab active={tab === "item"} onClick={() => setTab("item")}>{t("hints.tab.item")}</PillTab>
        <PillTab active={tab === "location"} onClick={() => setTab("location")}>{t("hints.tab.location")}</PillTab>
        <PillTab active={tab === "hints"} onClick={() => setTab("hints")}>
          {t("hints.tab.hints")} {snap.hints.length > 0 && <span className="ml-2 opacity-70">{snap.hints.length}</span>}
        </PillTab>
        <PillTab active={tab === "received"} onClick={() => setTab("received")}>
          {t("slot.tab.received")} {detail && detail.received_items.length > 0 && <span className="ml-2 opacity-70">{detail.received_items.length}</span>}
        </PillTab>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("hints.filter.placeholder")}
          className="w-full sm:ml-auto sm:w-64 h-10 rounded-md border hair-strong bg-surface px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2 focus:bg-canvas transition-colors duration-300"
        />
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-semantic-error/30 bg-card-rose px-4 py-3 text-body-sm text-semantic-error">
          {error}
        </div>
      )}

      <div className="mt-6 rounded-lg border hair bg-canvas transition-colors duration-300">
        {tab === "location" && (
          <ul className="divide-y hair-soft">
            {remainingLocations
              .filter((l) => l.name.toLowerCase().includes(search.toLowerCase()))
              .map((l) => (
                <li key={l.id} className="flex items-center gap-3 px-4 py-3">
                  <span className="h-1.5 w-1.5 rounded-pill bg-stone" />
                  <span className="text-body-sm text-ink">{l.name}</span>
                  <button
                    onClick={() => requestSubmit("location", l.name)}
                    disabled={busy === l.name}
                    className="ml-auto h-8 rounded-md bg-primary px-3 text-btn text-white hover:bg-primary-active disabled:opacity-60"
                  >
                    {busy === l.name ? "…" : t("hints.button.hint")}
                  </button>
                </li>
              ))}
            {remainingLocations.length === 0 && (
              <li className="px-4 py-8 text-center text-body-sm text-stone">{t("hints.empty.locations")}</li>
            )}
          </ul>
        )}

        {tab === "item" && (
          <ul className="divide-y hair-soft">
            {allItems
              .filter(({ name }) => name.toLowerCase().includes(search.toLowerCase()))
              .map(({ name, count }) => (
                <li key={name} className="flex items-center gap-3 px-4 py-3">
                  <span className="h-1.5 w-1.5 rounded-pill bg-stone" />
                  <span className="text-body-sm text-ink">{name}</span>
                  {count > 1 && (
                    <span className="inline-flex h-5 items-center rounded-pill bg-card-gray px-2 text-caption tabular-nums text-steel">
                      ×{count}
                    </span>
                  )}
                  <button
                    onClick={() => requestSubmit("item", name)}
                    disabled={busy === name}
                    className="ml-auto h-8 rounded-md bg-primary px-3 text-btn text-white hover:bg-primary-active disabled:opacity-60"
                  >
                    {busy === name ? "…" : t("hints.button.hint")}
                  </button>
                </li>
              ))}
            {allItems.length === 0 && (
              <li className="px-4 py-8 text-center text-body-sm text-stone">{t("hints.empty.items")}</li>
            )}
          </ul>
        )}

        {tab === "hints" && (
          <div>
            <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b hair-soft">
              <SubTab active={hintFilter === "mine_for"} onClick={() => setHintFilter("mine_for")}>{t("hints.subtab.mine_for")}</SubTab>
              <SubTab active={hintFilter === "mine_in"} onClick={() => setHintFilter("mine_in")}>{t("hints.subtab.mine_in")}</SubTab>
              <SubTab active={hintFilter === "all"} onClick={() => setHintFilter("all")}>{t("hints.subtab.all")}</SubTab>
              <Toggle
                className="ml-auto"
                label={t("hints.toggle.sort_tag")}
                checked={sortByTag}
                onChange={setSortByTag}
              />
              <Toggle
                label={t("hints.toggle.hide_found")}
                checked={hideFound}
                onChange={setHideFound}
              />
            </div>
            <div className="hidden sm:grid grid-cols-[1fr_1fr_160px_136px_72px] gap-x-4 px-4 py-2 text-caption-up uppercase text-steel border-b hair-soft">
              <div>{t("hints.col.item")}</div>
              <div>{t("hints.col.location")}</div>
              <div>{t("hints.col.parties")}</div>
              <div>{t("hints.col.tag")}</div>
              <div>{t("hints.col.status")}</div>
            </div>
            <ul className="divide-y hair-soft">
              {visibleHints.map((h, i) => {
                const finder = slotNames.get(h.finding_slot) ?? `slot ${h.finding_slot}`;
                const receiver = slotNames.get(h.receiving_slot) ?? `slot ${h.receiving_slot}`;
                const canTag = me.logged_in && h.receiving_slot === detail?.slot.slot;
                return (
                  <li
                    key={`${h.finding_slot}:${h.receiving_slot}:${h.item_id}:${h.location_id}:${i}`}
                    className="flex flex-col gap-1 px-4 py-3 text-body-sm sm:grid sm:grid-cols-[1fr_1fr_160px_136px_72px] sm:items-center sm:gap-x-4 sm:gap-y-0"
                  >
                    <span className="text-ink font-medium">{h.item_name}</span>
                    <span className="text-slate break-words">{h.location_name}</span>
                    <span className="text-steel tabular-nums text-caption sm:text-body-sm sm:truncate" title={`${finder} → ${receiver}`}>{finder} → {receiver}</span>
                    <span className="self-start sm:self-auto">
                      {canTag ? (
                        <TagMenu tag={h.tag} onPick={(tg) => updateTag(h, tg)} t={t} />
                      ) : h.tag ? (
                        <TagChip tag={h.tag} t={t} />
                      ) : (
                        <span className="text-caption text-stone">—</span>
                      )}
                    </span>
                    <span className={`self-start sm:self-auto inline-flex h-6 items-center rounded-pill px-2.5 text-caption-up uppercase ${
                      h.found ? "bg-card-mint text-brand-green" : "bg-card-gray text-steel"
                    }`}>
                      {h.found ? t("slot.status.found") : t("slot.status.open")}
                    </span>
                  </li>
                );
              })}
              {visibleHints.length === 0 && (
                <li className="px-4 py-8 text-center text-body-sm text-stone">
                  {hintFilter === "mine_for" && t("hints.empty.mine_for")}
                  {hintFilter === "mine_in"  && t("hints.empty.mine_in")}
                  {hintFilter === "all"      && t("hints.empty.all")}
                </li>
              )}
            </ul>
          </div>
        )}

        {tab === "received" && (
          <ul className="divide-y hair-soft">
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
        )}
      </div>

      {confirm && (() => {
        const total = detail?.slot.total ?? 0;
        const pct = snap.hint_cost ?? 10;
        const cost = Math.ceil((pct / 100) * total);
        const enough = me.hint_points >= cost;
        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-inkDeep/40 p-4"
            onClick={() => !busy && setConfirm(null)}
          >
            <div
              className="w-full max-w-md rounded-lg border hair bg-canvas p-6 shadow-mockup"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="text-title-md text-ink">{t("hints.confirm.title")}</h2>
              <p className="mt-2 text-body-sm text-slate">
                {t(confirm.kind === "item" ? "hints.confirm.body_item" : "hints.confirm.body_location", { target: confirm.target })}
              </p>
              <div className="mt-4 grid grid-cols-3 gap-3 text-body-sm">
                <Stat label={t("hints.confirm.cost")} value={`~${cost}`} />
                <Stat label={t("hints.confirm.balance")} value={String(me.hint_points)} />
                <Stat label={t("hints.confirm.after")} value={enough ? String(me.hint_points - cost) : "—"} />
              </div>
              <div className="mt-3 text-body-sm text-steel">
                {t("hints.confirm.note", { pct })}
                {!enough && <span className="ml-1 text-semantic-error">{t("hints.confirm.not_enough")}</span>}
              </div>
              <div className="mt-6 flex justify-end gap-3">
                <button
                  onClick={() => setConfirm(null)}
                  disabled={!!busy}
                  className="h-10 rounded-md border hair-strong bg-canvas px-5 text-btn text-ink hover:bg-surface disabled:opacity-60"
                >
                  {t("hints.confirm.cancel")}
                </button>
                <button
                  onClick={async () => {
                    const c = confirm;
                    await performSubmit(c.kind, c.target);
                    setConfirm(null);
                  }}
                  disabled={!!busy || !enough}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-5 text-btn text-white hover:bg-primary-active disabled:opacity-60"
                >
                  {busy && <FlowerSpinner size={18} color="#ffffff" />}
                  {busy ? t("hints.button.sending") : t("hints.confirm.confirm")}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-caption text-steel uppercase tracking-[0.06em]">{label}</div>
      <div className="text-title-sm text-ink tabular-nums">{value}</div>
    </div>
  );
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

function SubTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`h-7 rounded-pill px-3 text-caption-up uppercase tracking-wider transition-colors ${
        active ? "bg-primary text-white" : "bg-surface text-steel hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

const TAG_ORDER: HintTag[] = ["bked", "mandatory", "comfort"];

// Sort priority: tagged hints first in TAG_ORDER, untagged ("Others") last.
function tagRank(tag: HintTag | ""): number {
  const i = TAG_ORDER.indexOf(tag as HintTag);
  return i === -1 ? TAG_ORDER.length : i;
}

// Each tag gets a distinct, static colour (these tints don't theme-swap, so
// white text over them stays legible in both light and dark mode).
const TAG_CHIP: Record<HintTag, string> = {
  bked: "bg-brand-orange text-white",
  mandatory: "bg-semantic-error text-white",
  comfort: "bg-brand-teal text-white",
};
const TAG_DOT: Record<HintTag, string> = {
  bked: "bg-brand-orange",
  mandatory: "bg-semantic-error",
  comfort: "bg-brand-teal",
};

function TagChip({ tag, t }: { tag: HintTag; t: (k: string) => string }) {
  return (
    <span className={`inline-flex h-6 max-w-full items-center truncate rounded-pill px-2.5 text-caption-up uppercase ${TAG_CHIP[tag]}`}>
      {t(`hints.tag.${tag}`)}
    </span>
  );
}

function TagMenu({
  tag,
  onPick,
  t,
}: {
  tag: HintTag | "";
  onPick: (tag: HintTag | "") => void;
  t: (k: string) => string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t("hints.tag.set")}
        className="inline-flex h-6 max-w-full items-center gap-1 rounded-pill outline-none"
      >
        {tag ? (
          <TagChip tag={tag} t={t} />
        ) : (
          <span className="inline-flex h-6 items-center rounded-pill border border-dashed hair-strong px-2.5 text-caption-up uppercase text-steel hover:text-ink hover:border-primary">
            + {t("hints.col.tag")}
          </span>
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 z-50 mt-1 w-44 rounded-md border hair bg-canvas p-1 shadow-card">
            {TAG_ORDER.map((tg) => (
              <button
                key={tg}
                type="button"
                onClick={() => { onPick(tg); setOpen(false); }}
                className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left hover:bg-surface"
              >
                <span className={`h-2.5 w-2.5 shrink-0 rounded-pill ${TAG_DOT[tg]}`} />
                <span className="text-body-sm text-ink">{t(`hints.tag.${tg}`)}</span>
                {tag === tg && <span className="ml-auto text-primary">✓</span>}
              </button>
            ))}
            <button
              type="button"
              onClick={() => { onPick(""); setOpen(false); }}
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left hover:bg-surface"
            >
              <span className="h-2.5 w-2.5 shrink-0 rounded-pill border hair-strong" />
              <span className="text-body-sm text-slate">{t("hints.tag.none")}</span>
              {!tag && <span className="ml-auto text-primary">✓</span>}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
  className = "",
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  className?: string;
}) {
  return (
    <label className={`inline-flex cursor-pointer items-center gap-3 text-body-sm text-slate select-none ${className}`}>
      <span>{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-pill border transition-colors ${
          checked ? "bg-primary border-primary" : "bg-surface border-hairline-strong"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 rounded-pill bg-white shadow transition-transform ${
            checked ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </label>
  );
}
