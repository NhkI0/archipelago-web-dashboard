import { CSSProperties } from "react";

const ROTATIONS = [0, 60, 120, 180, 240, 300];

// Small inline version of the LoadingScreen flower-mark, scaled to `size`.
// The flower is authored for a 76×76 box, so we scale from that baseline.
export default function FlowerSpinner({ size = 20, color }: { size?: number; color?: string }) {
  const scale = size / 76;
  return (
    <span
      className="relative inline-block align-middle"
      style={{ width: size, height: size, ...(color ? ({ "--ls-accent": color } as CSSProperties) : {}) }}
      aria-hidden="true"
    >
      <span
        className="absolute left-0 top-0"
        style={{ width: 76, height: 76, transform: `scale(${scale})`, transformOrigin: "top left" }}
      >
        <span className="ls-flower-spin">
          {ROTATIONS.map((rot) => (
            <span key={rot} className="ls-petal-wrap" style={{ "--rot": `${rot}deg` } as CSSProperties}>
              <span className="ls-petal-orbit">
                <span className="ls-petal" />
              </span>
            </span>
          ))}
        </span>
      </span>
    </span>
  );
}
