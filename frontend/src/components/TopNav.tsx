import { Link, NavLink, useLocation } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, AvailableSlot, Me, Snapshot, liveSocket } from "../api";
import { useT } from "../i18n";
import { useConfig, getBasePath } from "../config";
import ThemeToggle from "./ThemeToggle";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `text-body-sm transition-colors ${isActive ? "text-ink" : "text-steel hover:text-ink"}`;

export default function TopNav() {
  const [me, setMe] = useState<Me | null>(null);
  const [open, setOpen] = useState(false);
  const [connectOpen, setConnectOpen] = useState(false);
  // position: fixed (not absolute) so the scrollable slot strip can't clip it.
  const [connectPos, setConnectPos] = useState<{ top: number; left: number } | null>(null);
  const [available, setAvailable] = useState<AvailableSlot[] | null>(null);
  const [busySlot, setBusySlot] = useState<string | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const { t, lang, setLang } = useT();
  const config = useConfig();
  const location = useLocation();
  const popRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe({ logged_in: false, slots: [] }));
  }, [location.pathname]);

  // Tracks the live snapshot so points update without a route change.
  useEffect(() => liveSocket((e) => { if (e?.snapshot) setSnap(e.snapshot); }), []);

  const livePointsFor = useMemo(() => {
    const m = new Map<string, number>();
    if (snap) for (const s of snap.slots) m.set(s.name, s.hint_points);
    return m;
  }, [snap]);

  useEffect(() => {
    if (me?.logged_in) api.slotsAvailable().then((r) => setAvailable(r.slots)).catch(() => setAvailable([]));
  }, [me?.logged_in]);

  // Close the "connect a slot" popover on an outside click.
  useEffect(() => {
    if (!connectOpen) return;
    function onDocClick(e: MouseEvent) {
      if (popRef.current && !popRef.current.contains(e.target as Node)) setConnectOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [connectOpen]);

  async function refreshAvailable() {
    try {
      setAvailable((await api.slotsAvailable()).slots);
    } catch {
      // leave the previous list showing rather than clear it on a blip
    }
  }

  async function connectSlot(name: string) {
    setBusySlot(name);
    setConnectError(null);
    try {
      setMe(await api.slotsAdd(name));
      await refreshAvailable();
      setConnectOpen(false);
    } catch (e: any) {
      setConnectError(e.message || String(e));
    } finally {
      setBusySlot(null);
    }
  }

  async function disconnectSlot(name: string) {
    setBusySlot(name);
    try {
      setMe(await api.slotsRemove(name));
      await refreshAvailable();
    } finally {
      setBusySlot(null);
    }
  }

  const notConnected = available?.filter((s) => !s.connected) ?? [];

  return (
    <header className="sticky top-0 z-30 border-b hair bg-canvas/95 backdrop-blur transition-colors duration-300">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2" onClick={() => setOpen(false)}>
          <img src={`${getBasePath()}/logo.svg`} alt="" aria-hidden className="h-7 w-7" />
          <span className="font-semibold tracking-tight text-ink">Archipelago</span>
        </Link>
        <nav className="ml-10 hidden items-center gap-7 md:flex">
          <NavLink to="/" end className={linkClass}>{t("nav.dashboard")}</NavLink>
          <NavLink to="/hints" className={linkClass}>{t("nav.hints")}</NavLink>
          {config.tracker.enabled && (
            <NavLink to="/tracker" className={linkClass}>{t("nav.tracker")}</NavLink>
          )}
          {config.features.hall_of_fame && (
            <NavLink to="/hall-of-fame" className={linkClass}>{t("nav.hof")}</NavLink>
          )}
        </nav>
        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <ThemeToggle />
          <button
            onClick={() => setLang(lang === "en" ? "fr" : "en")}
            className="h-9 rounded-md border hair-strong px-3 text-btn text-ink hover:bg-surface"
            aria-label="Switch language"
          >
            {t("common.lang.toggle")}
          </button>
          {me?.logged_in ? (
            <button
              onClick={async () => { await api.logout(); window.location.reload(); }}
              className="hidden sm:inline-flex h-9 items-center rounded-md border hair-strong bg-canvas px-4 text-btn text-ink hover:bg-surface transition-colors duration-300"
            >
              {t("nav.signout")}
            </button>
          ) : (
            <Link
              to="/login"
              state={{ from: location.pathname }}
              className="hidden sm:inline-flex h-9 items-center rounded-md bg-primary px-4 text-btn text-white hover:bg-primary-active"
            >
              {t("nav.signin")}
            </Link>
          )}
          <button
            type="button"
            aria-label="Toggle menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="md:hidden inline-flex h-9 w-9 items-center justify-center rounded-md border hair-strong text-ink hover:bg-surface"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              {open ? (
                <>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </>
              ) : (
                <>
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </>
              )}
            </svg>
          </button>
        </div>
      </div>
      {/* Connected slots live in their own scrollable strip below the main
          bar - a single flex row would overflow or squeeze the nav links as
          soon as more than one or two slots (or long slot names) are connected. */}
      {me?.logged_in && (
        <div className="hidden md:flex items-center gap-2 overflow-x-auto border-t hair-soft px-4 py-2 sm:px-6">
          {me.slots.map((s) => (
            <span
              key={s.slot}
              className="inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-pill bg-surface pl-3 pr-2 text-body-sm text-ink"
            >
              <span className="font-medium">{s.slot}</span>
              <span className="text-steel tabular-nums">{livePointsFor.get(s.slot) ?? s.hint_points} {t("nav.pts")}</span>
              {me.slots.length > 1 && (
                <button
                  type="button"
                  aria-label={t("nav.disconnect_slot", { slot: s.slot })}
                  onClick={() => disconnectSlot(s.slot)}
                  disabled={busySlot === s.slot}
                  className="ml-0.5 text-steel hover:text-semantic-error disabled:opacity-60"
                >
                  ✕
                </button>
              )}
            </span>
          ))}
          <div className="shrink-0" ref={popRef}>
            <button
              type="button"
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                setConnectPos({ top: rect.bottom + 4, left: rect.left });
                setConnectOpen((v) => !v);
              }}
              className="inline-flex h-8 items-center gap-1 whitespace-nowrap rounded-pill border border-dashed hair-strong px-3 text-body-sm text-steel hover:text-ink"
            >
              <span aria-hidden>+</span> {t("nav.connect_slot")}
            </button>
            {connectOpen && connectPos && (
              <div
                style={{ top: connectPos.top, left: connectPos.left }}
                className="fixed z-40 w-64 rounded-md border hair bg-canvas p-2 shadow-mockup"
              >
                {connectError && (
                  <div className="px-2 py-1 text-caption text-semantic-error">{connectError}</div>
                )}
                {available === null && <div className="px-2 py-2 text-caption text-steel">…</div>}
                {available && notConnected.length === 0 && (
                  <div className="px-2 py-2 text-caption text-steel">{t("nav.connect_slot.none")}</div>
                )}
                {notConnected.map((s) => (
                  <button
                    key={s.name}
                    type="button"
                    onClick={() => connectSlot(s.name)}
                    disabled={busySlot === s.name}
                    className="flex w-full items-center rounded-md px-2 py-1.5 text-left text-body-sm text-ink hover:bg-surface disabled:opacity-60"
                  >
                    {s.name}
                    <span className="ml-auto text-caption text-primary">{busySlot === s.name ? "…" : "→"}</span>
                  </button>
                ))}
                <div className="mt-1 px-2 text-caption text-stone">{t("nav.connect_slot.hint")}</div>
              </div>
            )}
          </div>
        </div>
      )}
      {open && (
        <div className="md:hidden border-t hair px-4 py-3 bg-canvas">
          <nav className="flex flex-col gap-3">
            <NavLink to="/" end className={linkClass} onClick={() => setOpen(false)}>{t("nav.dashboard")}</NavLink>
            <NavLink to="/hints" className={linkClass} onClick={() => setOpen(false)}>{t("nav.hints")}</NavLink>
            {config.tracker.enabled && (
              <NavLink to="/tracker" className={linkClass} onClick={() => setOpen(false)}>{t("nav.tracker")}</NavLink>
            )}
            {config.features.hall_of_fame && (
              <NavLink to="/hall-of-fame" className={linkClass} onClick={() => setOpen(false)}>{t("nav.hof")}</NavLink>
            )}
            {me?.logged_in ? (
              <>
                <div className="flex flex-col gap-1.5">
                  {me.slots.map((s) => (
                    <div key={s.slot} className="flex items-center gap-2 text-body-sm text-steel">
                      <span className="text-ink font-medium">{s.slot}</span>
                      <span className="tabular-nums">{livePointsFor.get(s.slot) ?? s.hint_points} {t("nav.hint_pts")}</span>
                      {me.slots.length > 1 && (
                        <button
                          type="button"
                          aria-label={t("nav.disconnect_slot", { slot: s.slot })}
                          onClick={() => disconnectSlot(s.slot)}
                          disabled={busySlot === s.slot}
                          className="ml-auto text-steel hover:text-semantic-error disabled:opacity-60"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                {notConnected.length > 0 && (
                  <div className="rounded-md border hair-soft p-2">
                    <div className="px-1 pb-1 text-caption-up uppercase text-steel">{t("nav.connect_slot")}</div>
                    {notConnected.map((s) => (
                      <button
                        key={s.name}
                        type="button"
                        onClick={() => connectSlot(s.name)}
                        disabled={busySlot === s.name}
                        className="flex w-full items-center rounded-md px-2 py-1.5 text-left text-body-sm text-ink hover:bg-surface disabled:opacity-60"
                      >
                        {s.name}
                        <span className="ml-auto text-caption text-primary">{busySlot === s.name ? "…" : "→"}</span>
                      </button>
                    ))}
                    {connectError && (
                      <div className="px-1 pt-1 text-caption text-semantic-error">{connectError}</div>
                    )}
                  </div>
                )}
                <button
                  onClick={async () => { await api.logout(); window.location.reload(); }}
                  className="h-9 self-start rounded-md border hair-strong bg-canvas px-4 text-btn text-ink hover:bg-surface"
                >
                  {t("nav.signout")}
                </button>
              </>
            ) : (
              <Link
                to="/login"
                state={{ from: location.pathname }}
                onClick={() => setOpen(false)}
                className="h-9 self-start inline-flex items-center rounded-md bg-primary px-4 text-btn text-white hover:bg-primary-active"
              >
                {t("nav.signin")}
              </Link>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
