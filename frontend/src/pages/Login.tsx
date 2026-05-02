import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Snapshot, api } from "../api";

export default function Login() {
  const nav = useNavigate();
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
      setError(err.message || "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative mx-auto max-w-md px-6 py-section">
      <div className="spotlight-glow" aria-hidden />
      <div className="relative rounded-xl border hair bg-surface-card p-12">
        <div className="text-caption-up uppercase text-primary-glow">Sign in</div>
        <h1 className="mt-3 text-display-sm text-bodyStrong">Log in as your slot</h1>
        <p className="mt-2 text-body-sm text-body">
          Required to spend hint points from the browser. Sessions are scoped to this device only.
        </p>
        <form onSubmit={submit} className="mt-8 space-y-4">
          <label className="block">
            <div className="mb-1 text-caption text-mutedSoft uppercase tracking-[0.08em]">Slot name</div>
            <input
              list="slot-options"
              value={slot}
              onChange={(e) => setSlot(e.target.value)}
              required
              className="h-11 w-full rounded-md bg-canvas-deep px-4 text-body-md text-bodyStrong outline-none focus:ring-1 focus:ring-primary-glow"
              placeholder="e.g. dopamine"
            />
            <datalist id="slot-options">
              {snap?.slots.map((s) => <option key={s.slot} value={s.name}>{s.game}</option>)}
            </datalist>
          </label>
          <label className="block">
            <div className="mb-1 text-caption text-mutedSoft uppercase tracking-[0.08em]">Password (if set)</div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-11 w-full rounded-md bg-canvas-deep px-4 text-body-md text-bodyStrong outline-none focus:ring-1 focus:ring-primary-glow"
              placeholder="optional"
            />
          </label>

          {error && <div className="text-body-sm text-semantic-error">{error}</div>}

          <button
            type="submit"
            disabled={busy}
            className="h-10 w-full rounded-md bg-primary text-btn text-white hover:bg-primary-active disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
