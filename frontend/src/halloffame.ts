// Sample Hall of Fame data for the static demo build only (no backend to serve
// host-dropped entries from there). A real deploy manages this via
// hall-of-fame/entries.toml + dropped images instead — see server/hall_of_fame.py.
import { HallOfFameEntry } from "./api";

export const HALL_OF_FAME: HallOfFameEntry[] = [
    { file: "Harcelement.png", artist: "Loïk", date: "2026-04-20", title: "Harcèlement.png" },
    { file: "crapo-archi1.jpg", artist: "Crapo", date: "2026-04-20" },
    { file: "red-rupee.png", artist: "Loïk", date: "2026-04-20" },
    { file: "baton.png", artist: "Loïk", date: "2026-05-17" },
    { file: "bodyRevelation.png", artist: "Loïk", date: "2026-07-12" },
    { file: "fixNumber1.png", artist: "Fix 👑", date: "2026-07-13" },
];
