import { Link, NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, Me } from "../api";
import { useT } from "../i18n";
import { useConfig } from "../config";
import ThemeToggle from "./ThemeToggle";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `text-body-sm transition-colors ${isActive ? "text-ink" : "text-steel hover:text-ink"}`;

export default function TopNav() {
  const [me, setMe] = useState<Me | null>(null);
  const [open, setOpen] = useState(false);
  const { t, lang, setLang } = useT();
  const config = useConfig();
  const location = useLocation();

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe({ logged_in: false }));
  }, [location.pathname]);

  return (
    <header className="sticky top-0 z-30 border-b hair bg-canvas/95 backdrop-blur transition-colors duration-300">
      <div className="mx-auto flex h-16 max-w-[1200px] items-center px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2" onClick={() => setOpen(false)}>
          <img src={`${import.meta.env.BASE_URL}logo.svg`} alt="" aria-hidden className="h-7 w-7" />
          <span className="font-semibold tracking-tight text-ink">Archipelago</span>
        </Link>
        <nav className="ml-10 hidden items-center gap-7 md:flex">
          <NavLink to="/" end className={linkClass}>{t("nav.dashboard")}</NavLink>
          <NavLink to="/hints" className={linkClass}>{t("nav.hints")}</NavLink>
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
            <>
              <span className="hidden lg:inline text-body-sm text-steel">
                {t("nav.slot")} <span className="text-ink font-medium">{me.slot}</span>
                <span className="ml-3">{t("nav.hint_pts")} </span>
                <span className="text-ink font-medium tabular-nums">{me.hint_points}</span>
              </span>
              <button
                onClick={async () => { await api.logout(); window.location.reload(); }}
                className="hidden sm:inline-flex h-9 items-center rounded-md border hair-strong bg-canvas px-4 text-btn text-ink hover:bg-surface transition-colors duration-300"
              >
                {t("nav.signout")}
              </button>
            </>
          ) : (
            <Link
              to="/login"
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
      {open && (
        <div className="md:hidden border-t hair px-4 py-3 bg-canvas">
          <nav className="flex flex-col gap-3">
            <NavLink to="/" end className={linkClass} onClick={() => setOpen(false)}>{t("nav.dashboard")}</NavLink>
            <NavLink to="/hints" className={linkClass} onClick={() => setOpen(false)}>{t("nav.hints")}</NavLink>
            {config.features.hall_of_fame && (
              <NavLink to="/hall-of-fame" className={linkClass} onClick={() => setOpen(false)}>{t("nav.hof")}</NavLink>
            )}
            {me?.logged_in ? (
              <>
                <span className="text-body-sm text-steel">
                  {t("nav.slot")} <span className="text-ink font-medium">{me.slot}</span>
                  <span className="ml-3">{t("nav.hint_pts")} </span>
                  <span className="text-ink font-medium tabular-nums">{me.hint_points}</span>
                </span>
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
