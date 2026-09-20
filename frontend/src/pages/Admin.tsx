import { FormEvent, useEffect, useState } from "react";
import { AdminStatus, adminApi, api } from "../api";

type ConnTab = "url" | "direct";

export default function Admin() {
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);

  const [tab, setTab] = useState<ConnTab>("direct");
  const [file, setFile] = useState<File | null>(null);
  const [roomUrl, setRoomUrl] = useState("");
  const [apHost, setApHost] = useState("");
  const [apPort, setApPort] = useState("");
  const [apPassword, setApPassword] = useState("");
  const [apSecure, setApSecure] = useState(true);
  const [hintCost, setHintCost] = useState("");
  const [defaultSlot, setDefaultSlot] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [restarting, setRestarting] = useState(false);

  function applyCurrent(s: AdminStatus) {
    setStatus(s);
    if (!s.current) return;
    setTab(s.current.room_url ? "url" : "direct");
    setRoomUrl(s.current.room_url);
    setApHost(s.current.ap_host);
    setApPort(s.current.ap_port ? String(s.current.ap_port) : "");
    setApSecure(s.current.ap_secure);
    setDefaultSlot(s.current.default_slot);
    setHintCost(s.current.hint_cost != null ? String(s.current.hint_cost) : "");
  }

  useEffect(() => {
    adminApi
      .status()
      .then(applyCurrent)
      .catch(() => setStatusError("This dashboard's admin panel is disabled. Set [admin].enabled = true in config.toml to use it."));
  }, []);

  async function submitLogin(e: FormEvent) {
    e.preventDefault();
    setLoginError(null);
    setLoggingIn(true);
    try {
      await adminApi.login(password);
      applyCurrent(await adminApi.status());
    } catch {
      setLoginError("Wrong password.");
    } finally {
      setLoggingIn(false);
    }
  }

  async function submitReconfigure(e: FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    if (!file) {
      setSubmitError("Choose a .archipelago (or generator .zip) file first.");
      return;
    }
    if (!status?.host_yaml_present) {
      const ok = tab === "url" ? roomUrl.trim() !== "" : apHost.trim() !== "" && apPort.trim() !== "";
      if (!ok) {
        setSubmitError(
          tab === "url" ? "Enter your archipelago.gg room URL." : "Enter both a server host and port."
        );
        return;
      }
    }
    setSubmitting(true);
    try {
      await adminApi.reconfigure({
        file,
        roomUrl: status?.host_yaml_present ? "" : tab === "url" ? roomUrl : "",
        apHost: status?.host_yaml_present ? "" : tab === "direct" ? apHost : "",
        apPort: status?.host_yaml_present ? "" : tab === "direct" ? apPort : "",
        apPassword: status?.host_yaml_present ? "" : apPassword,
        apSecure,
        hintCost,
        defaultSlot,
      });
      setRestarting(true);
      pollUntilBackUp();
    } catch (err: any) {
      setSubmitError(err?.message || "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  function pollUntilBackUp() {
    const tick = () => {
      api
        .config()
        .then(() => window.location.reload())
        .catch(() => setTimeout(tick, 1500));
    };
    setTimeout(tick, 1500);
  }

  if (restarting) {
    return (
      <div className="mx-auto max-w-md px-4 sm:px-6 py-12 sm:py-section text-center">
        <div className="rounded-lg border hair bg-canvas p-10 transition-colors duration-300">
          <h1 className="text-display-sm text-ink">Restarting…</h1>
          <p className="mt-2 text-body-sm text-slate">
            The dashboard is loading the new multiworld. This page will reload automatically once it's back.
          </p>
        </div>
      </div>
    );
  }

  if (statusError) {
    return (
      <div className="mx-auto max-w-md px-4 sm:px-6 py-12 sm:py-section">
        <div className="rounded-lg border hair bg-canvas p-6 sm:p-10 transition-colors duration-300">
          <p className="text-body-sm text-slate">{statusError}</p>
        </div>
      </div>
    );
  }

  if (!status) return null;

  if (!status.logged_in) {
    return (
      <div className="mx-auto max-w-md px-4 sm:px-6 py-12 sm:py-section">
        <div className="rounded-lg border hair bg-canvas p-6 sm:p-10 transition-colors duration-300">
          <div className="text-caption-up uppercase text-primary">Admin</div>
          <h1 className="mt-3 text-display-sm text-ink">Sign in</h1>
          <form onSubmit={submitLogin} className="mt-8 space-y-5">
            <label className="block">
              <div className="mb-1.5 text-body-sm font-medium text-charcoal">Admin password</div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
                className="h-11 w-full rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
              />
            </label>
            {loginError && <div className="text-body-sm text-semantic-error">{loginError}</div>}
            <button
              type="submit"
              disabled={loggingIn}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary text-btn text-white hover:bg-primary-active disabled:opacity-60"
            >
              {loggingIn ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 sm:px-6 py-12 sm:py-section">
      <div className="rounded-lg border hair bg-canvas p-6 sm:p-10 transition-colors duration-300">
        <div className="text-caption-up uppercase text-primary">Admin</div>
        <h1 className="mt-3 text-display-sm text-ink">Change the running multiworld</h1>
        <p className="mt-2 text-body-sm text-slate">
          Uploading a new file replaces the game in progress. The dashboard restarts to pick it up
          (a few seconds of downtime) and previous death/item/hint logs are archived, not deleted.
        </p>

        <form onSubmit={submitReconfigure} className="mt-8 space-y-5">
          <label className="block">
            <div className="mb-1.5 text-body-sm font-medium text-charcoal">Multidata file</div>
            <input
              type="file"
              accept=".archipelago,.zip"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-body-sm text-ink"
            />
            <div className="mt-1 text-body-sm text-stone">
              A .archipelago file, or the generator's .zip output.
            </div>
          </label>

          {status.host_yaml_present ? (
            <div className="text-body-sm text-slate">
              A local host.yaml was found: this dashboard already connects to your own AP server, so
              host/port/password aren't editable here.
            </div>
          ) : (
            <div>
              <div className="mb-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => setTab("url")}
                  className={`h-9 flex-1 rounded-md text-body-sm font-medium ${tab === "url" ? "bg-primary text-white" : "border hair text-charcoal"}`}
                >
                  archipelago.gg link
                </button>
                <button
                  type="button"
                  onClick={() => setTab("direct")}
                  className={`h-9 flex-1 rounded-md text-body-sm font-medium ${tab === "direct" ? "bg-primary text-white" : "border hair text-charcoal"}`}
                >
                  Host &amp; port
                </button>
              </div>

              {tab === "url" ? (
                <label className="block">
                  <div className="mb-1.5 text-body-sm font-medium text-charcoal">archipelago.gg room URL</div>
                  <input
                    type="text"
                    value={roomUrl}
                    onChange={(e) => setRoomUrl(e.target.value)}
                    placeholder="https://archipelago.gg/room/XXXXXXXXXXXXXXXXXXXX"
                    className="h-11 w-full rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
                  />
                </label>
              ) : (
                <div className="space-y-3">
                  <label className="block">
                    <div className="mb-1.5 text-body-sm font-medium text-charcoal">Server host</div>
                    <input
                      type="text"
                      value={apHost}
                      onChange={(e) => setApHost(e.target.value)}
                      placeholder="myMultiworldAddress.com"
                      className="h-11 w-full rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
                    />
                  </label>
                  <label className="block">
                    <div className="mb-1.5 text-body-sm font-medium text-charcoal">Port</div>
                    <input
                      type="number"
                      value={apPort}
                      onChange={(e) => setApPort(e.target.value)}
                      placeholder="38281"
                      className="h-11 w-full rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
                    />
                  </label>
                  <label className="flex items-center gap-2 text-body-sm text-charcoal">
                    <input type="checkbox" checked={apSecure} onChange={(e) => setApSecure(e.target.checked)} />
                    Secure connection (wss://), leave on for archipelago.gg
                  </label>
                </div>
              )}

              <label className="mt-3 block">
                <div className="mb-1.5 text-body-sm font-medium text-charcoal">Server password (optional)</div>
                <input
                  type="password"
                  value={apPassword}
                  onChange={(e) => setApPassword(e.target.value)}
                  placeholder="leave blank to keep the current one"
                  className="h-11 w-full rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
                />
              </label>

              <label className="mt-3 block">
                <div className="mb-1.5 text-body-sm font-medium text-charcoal">
                  Hint cost % <span className="font-normal">(optional, only if you host the AP server yourself)</span>
                </div>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={hintCost}
                  onChange={(e) => setHintCost(e.target.value)}
                  className="h-11 w-32 rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
                />
              </label>
            </div>
          )}

          <label className="block">
            <div className="mb-1.5 text-body-sm font-medium text-charcoal">
              Default slot <span className="font-normal">(optional)</span>
            </div>
            <input
              type="text"
              value={defaultSlot}
              onChange={(e) => setDefaultSlot(e.target.value)}
              placeholder="auto-pick"
              className="h-11 w-full rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
            />
          </label>

          {submitError && <div className="text-body-sm text-semantic-error">{submitError}</div>}

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-primary text-btn text-white hover:bg-primary-active disabled:opacity-60"
          >
            {submitting ? "Applying…" : "Replace multiworld & restart"}
          </button>
        </form>
      </div>
    </div>
  );
}
