import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Snapshot, api } from "../api";
import { useT } from "../i18n";

export default function Login() {
  const nav = useNavigate();
  const { t } = useT();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [slot, setSlot] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.state().then(setSnap).catch(console.error); }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.login(slot, password);
      nav("/hints");
    } catch (err: any) {
      setError(err.message || t("login.error.default"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-6 py-section">
      <div className="rounded-lg border hair bg-canvas p-10 transition-colors duration-300">
        <div className="text-caption-up uppercase text-primary">{t("login.kicker")}</div>
        <h1 className="mt-3 text-display-sm text-ink">{t("login.title")}</h1>
        <p className="mt-2 text-body-sm text-slate">{t("login.body")}</p>
        <form onSubmit={submit} className="mt-8 space-y-5">
          <label className="block">
            <div className="mb-1.5 text-body-sm font-medium text-charcoal">{t("login.field.slot")}</div>
            <input
              list="slot-options"
              value={slot}
              onChange={(e) => setSlot(e.target.value)}
              required
              className="h-11 w-full rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
              placeholder={t("login.placeholder.slot")}
            />
            <datalist id="slot-options">
              {snap?.slots.map((s) => <option key={s.slot} value={s.name}>{s.game}</option>)}
            </datalist>
          </label>
          <label className="block">
            <div className="mb-1.5 text-body-sm font-medium text-charcoal">{t("login.field.password")}</div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-11 w-full rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
              placeholder={t("login.placeholder.password")}
            />
          </label>

          {error && <div className="text-body-sm text-semantic-error">{error}</div>}

          <button
            type="submit"
            disabled={busy}
            className="h-10 w-full rounded-md bg-primary text-btn text-white hover:bg-primary-active disabled:opacity-60"
          >
            {busy ? t("login.button.signing") : t("login.button.signin")}
          </button>
        </form>
      </div>
    </div>
  );
}
