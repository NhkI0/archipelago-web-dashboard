// Hashed from the slot name so a player keeps the same color across reloads, unlike an index-based cycle.

const PLAYER_PALETTE = [
  "text-brand-orange",
  "text-semantic-error",
  "text-brand-teal",
  "text-primary",
  "text-brand-pink",
  "text-brand-green",
];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

export function colorForSlot(slot: string): string {
  return PLAYER_PALETTE[hashString(slot) % PLAYER_PALETTE.length];
}
