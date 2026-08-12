// Sample Hall of Fame data for the static demo build only (no backend to serve
// host-dropped entries from there). A real deploy manages this via
// hall-of-fame/entries.toml + dropped images instead — see server/hall_of_fame.py.
import { HallOfFameEntry } from "../api";

export const HALL_OF_FAME: HallOfFameEntry[] = [
    { file: "red-rupee.png", artist: "JDLo", date: "2026-04-20" },
    { file: "bodyRevelation.png", artist: "JDLo", date: "2026-07-12" },
    { file: "fixNumber1.png", artist: "Fix 👑", date: "2026-07-13" },
];
