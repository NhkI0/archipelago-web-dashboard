import { useState } from "react";
import { gameMeta } from "../games";

type Props = {
  game: string;
  size?: number;
  className?: string;
};

export default function GameIcon({ game, size = 24, className = "" }: Props) {
  const { slug, emoji } = gameMeta(game);
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span
        aria-label={game}
        className={className}
        style={{ fontSize: Math.round(size * 0.95), lineHeight: 1, display: "inline-block" }}
      >
        {emoji}
      </span>
    );
  }

  return (
    <img
      src={`/games/${slug}.png`}
      alt={game}
      width={size}
      height={size}
      onError={() => setFailed(true)}
      className={className}
      style={{ objectFit: "contain" }}
    />
  );
}
