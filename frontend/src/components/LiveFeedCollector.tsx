import { useEffect, useRef } from "react";
import { CheckEvent, Hint, liveSocket } from "../api";
import { markFeedReady, nextFeedId, pushFeedItem, resetFeed } from "../liveFeedStore";

// Mounted once at the Shell level (see App.tsx) so it keeps capturing events no matter which page is open.
export default function LiveFeedCollector() {
  const slotInfo = useRef<Map<number, { name: string; game: string }>>(new Map());

  useEffect(() => {
    const handle = (e: any) => {
      if (e?.type === "check" && Array.isArray(e.checks)) {
        for (const c of e.checks as CheckEvent[]) {
          pushFeedItem({
            kind: "check",
            id: nextFeedId("c"),
            ts: c.ts,
            finder: c.finder_name,
            finderGame: c.finder_game,
            recv: c.recv_name,
            recvGame: c.recv_game,
            item: c.item_name,
            location: c.location_name,
          });
        }
      } else if (e?.type === "hint" && e.hint) {
        const h = e.hint as Hint;
        const finder = slotInfo.current.get(h.finding_slot)?.name ?? `slot ${h.finding_slot}`;
        const recv = slotInfo.current.get(h.receiving_slot)?.name ?? `slot ${h.receiving_slot}`;
        pushFeedItem({
          kind: "hint",
          id: nextFeedId("h"),
          ts: e.ts ?? Date.now() / 1000,
          finder,
          recv,
          item: h.item_name,
          location: h.location_name,
        });
      } else if (e?.type === "goal" && typeof e.slot === "number") {
        const info = slotInfo.current.get(e.slot);
        pushFeedItem({
          kind: "goal",
          id: nextFeedId("g"),
          ts: e.ts ?? Date.now() / 1000,
          name: info?.name ?? `slot ${e.slot}`,
          game: info?.game ?? "",
        });
      }
    };

    return liveSocket((e: any) => {
      markFeedReady();
      if (e?.snapshot) {
        slotInfo.current = new Map(e.snapshot.slots.map((s: any) => [s.slot, { name: s.name, game: s.game }]));
      }
      if (e?.type === "feed_history" && Array.isArray(e.events)) {
        // Server history replaces the local list, so reconnects never duplicate rows.
        resetFeed();
        for (const ev of e.events) handle(ev);
        return;
      }
      handle(e);
    });
  }, []);

  return null;
}
