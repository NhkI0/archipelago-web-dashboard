import { useEffect, useRef, useState } from "react";
import { Hint, api, liveSocket } from "../api";

type Toast = { id: number; text: string };

function hintKey(h: Hint) {
  return `${h.finding_slot}:${h.receiving_slot}:${h.item_id}:${h.location_id}`;
}

export default function HintNotifier() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seen = useRef<Set<string>>(new Set());
  const mySlot = useRef<number | null>(null);
  const slotNames = useRef<Map<number, string>>(new Map());
  const initial = useRef<boolean>(true);
  const counter = useRef<number>(0);

  function notify(text: string) {
    const id = ++counter.current;
    setToasts((t) => [...t, { id, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
    // Favicon "ping": title bar marker for inactive tabs.
    if (typeof document !== "undefined" && document.hidden) {
      const orig = document.title;
      document.title = "● " + orig;
      const restore = () => {
        document.title = orig;
        document.removeEventListener("visibilitychange", restore);
      };
      document.addEventListener("visibilitychange", restore);
    }
  }

  function ingestSnapshot(snap: { hints: Hint[]; slots: { slot: number; name: string }[] }) {
    slotNames.current = new Map(snap.slots.map((s) => [s.slot, s.name]));
    for (const h of snap.hints) {
      const k = hintKey(h);
      if (!seen.current.has(k)) {
        if (!initial.current && mySlot.current !== null && h.receiving_slot === mySlot.current) {
          const finder = slotNames.current.get(h.finding_slot) ?? `slot ${h.finding_slot}`;
          notify(`Hint for you: ${h.item_name} — in ${finder}'s world (${h.location_name})`);
        }
        seen.current.add(k);
      }
    }
    initial.current = false;
  }

  useEffect(() => {
    let cancelled = false;

    api.me().then((m) => {
      if (cancelled) return;
      if (m.logged_in) {
        // Resolve slot id for this player's slot name.
        api.state().then((s) => {
          if (cancelled) return;
          const found = s.slots.find((sl) => sl.name === m.slot);
          mySlot.current = found?.slot ?? null;
          ingestSnapshot(s);
        });
      } else {
        // Still warm the seen-set so we don't toast on first login.
        api.state().then((s) => !cancelled && ingestSnapshot(s));
      }
    });

    const stop = liveSocket((e) => {
      if (e?.snapshot) ingestSnapshot(e.snapshot);
    });

    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="pointer-events-auto max-w-sm rounded-md border hair bg-surface-card px-4 py-3 text-body-sm text-bodyStrong shadow-lg"
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}
