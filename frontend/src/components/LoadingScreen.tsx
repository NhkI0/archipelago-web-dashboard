import { CSSProperties } from "react";
import { useT } from "../i18n";

const ROTATIONS = [0, 60, 120, 180, 240, 300];

// Flips true once the app has successfully loaded data for the first time.
// Before that, the splash takes over the whole screen (initial connection);
let connectedOnce = false;
export const markConnected = () => {
  connectedOnce = true;
};

export default function LoadingScreen() {
  const { t } = useT();
  const fullScreen = !connectedOnce;

  const rootClass = fullScreen
    ? "fixed inset-0 z-50 flex flex-col items-center justify-center gap-7 bg-canvas transition-colors duration-300"
    : "flex min-h-[70vh] w-full flex-col items-center justify-center gap-7";

  return (
    <div className={rootClass} role="status" aria-live="polite" aria-label={t("loading.tag")}>
      <div className="relative" style={{ width: 76, height: 76 }}>
        <div className="ls-flower-spin">
          {ROTATIONS.map((rot) => (
            <div key={rot} className="ls-petal-wrap" style={{ "--rot": `${rot}deg` } as CSSProperties}>
              <div className="ls-petal-orbit">
                <div className="ls-petal" />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="text-center">
        <div className="ls-brand-word text-[22px] font-semibold text-ink" style={{ letterSpacing: "-0.2px" }}>
          {t("loading.brand")}
        </div>
        <div className="ls-brand-tag mt-1.5 text-[13px] text-stone">
          {t("loading.tag")}
        </div>
      </div>

      <div className="overflow-hidden rounded-pill bg-hairline" style={{ width: 180, height: 3 }}>
        <div className="ls-track-fill h-full rounded-pill" style={{ width: "60%" }} />
      </div>
    </div>
  );
}
