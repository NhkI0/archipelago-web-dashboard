// Hall of Fame manifest.
//
// To add a new piece:
//   1. Drop the image file into  web/frontend/public/hall-of-fame/<filename>
//   2. Append a row below.
//
// Newest entries can go anywhere — the page sorts by date descending.

export type HallEntry = {
  /** Filename inside /hall-of-fame/. */
  file: string;
  /** Credit shown under the piece. */
  artist: string;
  /** ISO date — YYYY-MM-DD. Used for sorting and display. */
  date: string;
  /** Optional title / caption. */
  title?: string;
};

export const HALL_OF_FAME: HallEntry[] = [
  // Example — replace or remove:
  // { file: "first.png", artist: "Dialesse", date: "2026-05-04", title: "Power-Star portrait" },
    { file: "Harcelement.png", artist: "Loïk", date: "2026-04-20", title: "Harcèlement.png" },
    { file: "crapo-archi1.jpg", artist: "Crapo", date: "2026-04-20" },
    { file: "red-rupee.png", artist: "Loïk", date: "2026-04-20" },
];
