import { Link, NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, Me } from "../api";
import { useT } from "../i18n";
import ThemeToggle from "./ThemeToggle";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `text-body-sm transition-colors ${isActive ? "text-ink" : "text-steel hover:text-ink"}`;

export default function TopNav() {
  const [me, setMe] = useState<Me | null>(null);
  const { t, lang, setLang } = useT();

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe({ logged_in: false }));
  }, []);

  return (
    <header className="sticky top-0 z-30 h-16 border-b hair bg-canvas/95 backdrop-blur transition-colors duration-300">
      <div className="mx-auto flex h-full max-w-[1200px] items-center px-6">
        <Link to="/" className="flex items-center gap-2">
          <img src="/favicon.ico" alt="" aria-hidden className="h-7 w-7 rounded-md" />
          <span className="font-semibold tracking-tight text-ink">{t("nav.brand")}</span>
        </Link>
        <nav className="ml-10 flex items-center gap-7">
          <NavLink to="/" end className={linkClass}>{t("nav.dashboard")}</NavLink>
          <NavLink to="/hints" className={linkClass}>{t("nav.hints")}</NavLink>
          <NavLink to="/hall-of-fame" className={linkClass}>{t("nav.hof")}</NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3">
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
              <span className="text-body-sm text-steel">
                {t("nav.slot")} <span className="text-ink font-medium">{me.slot}</span>
                <span className="ml-3">{t("nav.hint_pts")} </span>
                <span className="text-ink font-medium tabular-nums">{me.hint_points}</span>
              </span>
              <button
                onClick={async () => { await api.logout(); location.reload(); }}
                className="h-9 rounded-md border hair-strong bg-canvas px-4 text-btn text-ink hover:bg-surface transition-colors duration-300"
              >
                {t("nav.signout")}
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="h-9 inline-flex items-center rounded-md bg-primary px-4 text-btn text-white hover:bg-primary-active"
            >
              {t("nav.signin")}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
