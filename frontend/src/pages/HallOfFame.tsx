import { useEffect, useMemo, useState } from "react";
import { HALL_OF_FAME, HallEntry } from "../halloffame";
import { useT } from "../i18n";

export default function HallOfFame() {
  const { t, lang } = useT();
  const [open, setOpen] = useState<HallEntry | null>(null);

  const entries = useMemo(
    () => [...HALL_OF_FAME].sort((a, b) => (a.date < b.date ? 1 : -1)),
    [],
  );

  const fmt = useMemo(
    () => new Intl.DateTimeFormat(lang, { dateStyle: "long" }),
    [lang],
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="mx-auto max-w-[1200px] px-4 sm:px-6 py-12 sm:py-section">
      <header className="mb-8 sm:mb-10 text-center">
        <div className="text-caption-up uppercase text-primary">{t("hof.kicker")}</div>
        <h1 className="mt-2 text-display-sm sm:text-display-md text-ink">{t("hof.title")}</h1>
        <p className="mx-auto mt-3 max-w-xl text-body-md text-slate">{t("hof.intro")}</p>
      </header>

      {entries.length === 0 ? (
        <div className="rounded-lg border hair bg-canvas px-6 py-12 text-center text-body-sm text-stone transition-colors duration-300">
          {t("hof.empty")}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {entries.map((e) => (
            <button
              key={e.file}
              type="button"
              onClick={() => setOpen(e)}
              className="group block w-full overflow-hidden rounded-lg border hair bg-canvas text-left transition-colors duration-300 hover:shadow-card"
            >
              <div className="flex items-center justify-center bg-surface" style={{ aspectRatio: "3 / 4" }}>
                <img
                  src={`/hall-of-fame/${e.file}`}
                  alt={e.title || `${t("hof.by")} ${e.artist}`}
                  className="max-h-full max-w-full object-contain transition-opacity group-hover:opacity-95"
                  loading="lazy"
                />
              </div>
              <div className="p-4 text-center">
                {e.title && <div className="text-title-sm text-ink">{e.title}</div>}
                <div className="mt-1 text-body-sm text-slate">
                  <span className="text-stone">{t("hof.by")} </span>
                  <span className="font-medium text-ink">{e.artist}</span>
                </div>
                <div className="mt-1 font-mono text-caption text-stone">{fmt.format(new Date(e.date))}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-inkDeep/70 p-6"
          onClick={() => setOpen(null)}
          role="dialog"
          aria-modal="true"
        >
          <figure
            onClick={(e) => e.stopPropagation()}
            className="max-h-full max-w-[1200px] overflow-hidden rounded-lg border hair bg-canvas shadow-mockup"
          >
            <img
              src={`/hall-of-fame/${open.file}`}
              alt={open.title || `${t("hof.by")} ${open.artist}`}
              className="block max-h-[78vh] w-auto object-contain"
            />
            <figcaption className="flex items-baseline justify-between gap-4 border-t hair px-5 py-3 text-body-sm">
              <span>
                {open.title && <span className="font-medium text-ink">{open.title} · </span>}
                <span className="text-stone">{t("hof.by")} </span>
                <span className="text-ink">{open.artist}</span>
              </span>
              <span className="font-mono text-caption text-stone">{fmt.format(new Date(open.date))}</span>
            </figcaption>
          </figure>
        </div>
      )}
    </div>
  );
}
