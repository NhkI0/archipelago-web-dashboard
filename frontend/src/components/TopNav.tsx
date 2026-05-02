import { Link, NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, Me } from "../api";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `text-body-sm transition-colors ${isActive ? "text-bodyStrong" : "text-body hover:text-bodyStrong"}`;

export default function TopNav() {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe({ logged_in: false }));
  }, []);

  return (
    <header className="sticky top-0 z-30 h-16 border-b hair bg-canvas/95 backdrop-blur">
      <div className="mx-auto flex h-full max-w-[1200px] items-center px-6">
        <Link to="/" className="flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 rounded-pill bg-primary shadow-[0_0_10px_#1a26ff]" />
          <span className="font-medium tracking-tight text-bodyStrong">Archipelago</span>
        </Link>
        <nav className="ml-10 flex items-center gap-7">
          <NavLink to="/" end className={linkClass}>Dashboard</NavLink>
          <NavLink to="/hints" className={linkClass}>Hint Manager</NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {me?.logged_in ? (
            <>
              <span className="text-body-sm text-body">
                <span className="text-mutedSoft">slot </span>
                <span className="text-bodyStrong">{me.slot}</span>
                <span className="ml-3 text-mutedSoft">hint pts </span>
                <span className="text-bodyStrong">{me.hint_points}</span>
              </span>
              <button
                onClick={async () => { await api.logout(); location.reload(); }}
                className="h-9 rounded-md border hair-strong px-4 text-btn text-body hover:text-bodyStrong"
              >
                Sign out
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="h-9 inline-flex items-center rounded-md bg-primary px-4 text-btn text-white hover:bg-primary-active"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
