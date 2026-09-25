import { DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Me, TrackerMineSlot, TrackerResult, api, liveSocket, onMeChanged, trackerApi } from "../api";
import LoadingScreen, { markConnected } from "../components/LoadingScreen";
import FlowerSpinner from "../components/FlowerSpinner";
import { useT } from "../i18n";

// Outside the component so a run's result survives leaving /tracker and coming back.
const resultCache: Record<string, TrackerResult> = {};

function withoutChecked(result: TrackerResult, checkedIds: Set<number>): TrackerResult {
  const locations = result.locations.filter((l) => !checkedIds.has(l.id));
  if (locations.length === result.locations.length) return result;
  const removed = result.locations.length - locations.length;
  return {
    ...result,
    checked: result.checked + removed,
    remaining: locations.length,
    accessible: locations.filter((l) => l.accessible).length,
    locations,
  };
}

// Fetches live checked state and prunes it from the cached result.
function pruneAgainstLive(slot: string, setResult: (fn: (prev: TrackerResult | null) => TrackerResult | null) => void) {
  api
    .slot(slot)
    .then((d) => {
      const checkedIds = new Set(d.locations.filter((l) => l.checked).map((l) => l.id));
      setResult((prev) => {
        if (!prev) return prev;
        const next = withoutChecked(prev, checkedIds);
        resultCache[slot] = next;
        return next;
      });
    })
    .catch(() => {});
}

export default function Tracker() {
  const { t } = useT();
  const location = useLocation();
  const [me, setMe] = useState<Me | null>(null);
  const [mine, setMine] = useState<TrackerMineSlot[] | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [viewingSlot, setViewingSlot] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<TrackerResult | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe({ logged_in: false, slots: [] }));
  }, []);

  // A slot connected/disconnected from TopNav while this page is already mounted.
  useEffect(() => onMeChanged(setMe), []);

  function refreshMine() {
    trackerApi
      .mine()
      .then((r) => {
        setMine(r.slots);
        setDisabled(false);
      })
      .catch(() => setDisabled(true));
  }

  const mySlotKey = me?.logged_in ? me.slots.map((s) => s.slot).join(",") : "";

  useEffect(() => {
    if (me?.logged_in) refreshMine();
  }, [mySlotKey]);

  useEffect(() => {
    if (!me?.logged_in) {
      setViewingSlot(null);
      return;
    }
    if (viewingSlot && me.slots.some((s) => s.slot === viewingSlot)) return;
    setViewingSlot(me.slots[0]?.slot ?? null);
  }, [me]);

  useEffect(() => {
    setResult((viewingSlot && resultCache[viewingSlot]) || null);
    setRunError(null);
    setFile(null);
    setUploadError(null);
  }, [viewingSlot]);

  // Reconcile the cache against whatever got checked while this page wasn't mounted.
  useEffect(() => {
    if (!viewingSlot || !resultCache[viewingSlot]) return;
    pruneAgainstLive(viewingSlot, setResult);
  }, [viewingSlot]);

  // Debounced: a busy room broadcasts a check often enough to hammer /api/slot otherwise.
  useEffect(() => {
    if (!viewingSlot) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const stop = liveSocket(() => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => pruneAgainstLive(viewingSlot, setResult), 2000);
    });
    return () => {
      if (timer) clearTimeout(timer);
      stop();
    };
  }, [viewingSlot]);

  useEffect(() => {
    if (me !== null) markConnected();
  }, [me]);

  const hasYaml = useMemo(
    () => mine?.find((s) => s.slot === viewingSlot)?.has_yaml ?? false,
    [mine, viewingSlot],
  );

  const visibleLocations = useMemo(() => {
    if (!result) return [];
    const q = search.toLowerCase();
    return result.locations.filter((l) => !q || l.name.toLowerCase().includes(q));
  }, [result, search]);

  async function submitUpload(e: FormEvent) {
    e.preventDefault();
    if (!viewingSlot || !file) return;
    setUploading(true);
    setUploadError(null);
    try {
      await trackerApi.uploadYaml(viewingSlot, file);
      setFile(null);
      refreshMine();
    } catch (err: any) {
      setUploadError(err?.message || String(err));
    } finally {
      setUploading(false);
    }
  }

  async function runTracker() {
    if (!viewingSlot) return;
    setRunning(true);
    setRunError(null);
    try {
      const r = await trackerApi.run(viewingSlot);
      resultCache[viewingSlot] = r;
      setResult(r);
    } catch (err: any) {
      setRunError(err?.message || t("tracker.error.default"));
    } finally {
      setRunning(false);
    }
  }

  if (me === null) {
    return <LoadingScreen />;
  }

  if (!me.logged_in) {
    return (
      <div className="mx-auto max-w-md px-6 py-section text-center">
        <h1 className="text-display-sm text-ink">{t("tracker.signin_title")}</h1>
        <p className="mt-2 text-body-sm text-slate">{t("tracker.signin_body")}</p>
        <Link
          to="/login"
          state={{ from: location.pathname }}
          className="mt-6 inline-flex h-10 items-center rounded-md bg-primary px-5 text-btn text-white hover:bg-primary-active"
        >
          {t("nav.signin")}
        </Link>
      </div>
    );
  }

  if (disabled) {
    return (
      <div className="mx-auto max-w-md px-4 sm:px-6 py-12 sm:py-section">
        <div className="rounded-lg border hair bg-canvas p-6 sm:p-10 transition-colors duration-300">
          <div className="text-caption-up uppercase text-primary">{t("tracker.disabled_title")}</div>
          <p className="mt-3 text-body-sm text-slate">{t("tracker.disabled_body")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1200px] px-4 sm:px-6 py-12">
      <header className="flex flex-wrap items-end gap-6 border-b hair pb-8">
        <div>
          <div className="text-caption-up uppercase text-primary">{t("tracker.kicker")}</div>
          <h1 className="mt-2 text-display-sm sm:text-display-md text-ink">{t("tracker.title")}</h1>
          <p className="mt-2 max-w-xl text-body-sm text-slate">{t("tracker.intro")}</p>
          {me.slots.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {me.slots.map((s) => (
                <button
                  key={s.slot}
                  type="button"
                  onClick={() => setViewingSlot(s.slot)}
                  className={`h-7 rounded-pill px-3 text-caption-up uppercase tracking-wider transition-colors ${
                    s.slot === viewingSlot ? "bg-primary text-white" : "bg-surface text-steel hover:text-ink"
                  }`}
                >
                  {s.slot}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      {!hasYaml ? (
        <div className="mt-8 rounded-lg border hair bg-canvas p-6 transition-colors duration-300">
          <h2 className="text-title-md text-ink">{t("tracker.yaml.missing_title")}</h2>
          <p className="mt-1 text-body-sm text-slate">{t("tracker.yaml.missing_body")}</p>
          <form onSubmit={submitUpload} className="mt-4">
            <YamlDropzone file={file} onFile={setFile} disabled={uploading} />
            <div className="mt-4 flex items-center justify-end">
              <button
                type="submit"
                disabled={!file || uploading}
                className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-btn text-white hover:bg-primary-active disabled:opacity-60"
              >
                {uploading && <FlowerSpinner size={16} color="#ffffff" />}
                {uploading ? t("tracker.yaml.uploading") : t("tracker.yaml.button")}
              </button>
            </div>
          </form>
          {uploadError && <div className="mt-3 text-body-sm text-semantic-error">{uploadError}</div>}
        </div>
      ) : (
        <>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <span className="text-body-sm text-slate">{t("tracker.yaml.uploaded")}</span>
            <button
              type="button"
              onClick={runTracker}
              disabled={running}
              className="ml-auto inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-5 text-btn text-white hover:bg-primary-active disabled:opacity-60"
            >
              {running && <FlowerSpinner size={18} color="#ffffff" />}
              {running ? t("tracker.run.running") : result ? t("tracker.run.rerun") : t("tracker.run.button")}
            </button>
          </div>

          {runError && (
            <div className="mt-4 rounded-md border border-semantic-error/30 bg-card-rose px-4 py-3 text-body-sm text-semantic-error">
              {runError}
            </div>
          )}

          {result && (
            <>
              <div className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-3 rounded-lg bg-surface px-5 py-4 text-body-sm transition-colors duration-300">
                <Stat label={t("tracker.stat.total")} value={String(result.total)} />
                <Stat label={t("tracker.stat.checked")} value={String(result.checked)} />
                <Stat label={t("tracker.stat.remaining")} value={String(result.remaining)} />
                <Stat label={t("tracker.stat.accessible")} value={String(result.accessible)} />
              </div>

              <div className="mt-6">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t("tracker.search")}
                  className="h-10 w-full sm:w-64 rounded-md border hair-strong bg-canvas px-4 text-body-md text-ink placeholder:text-stone outline-none focus:border-primary focus:border-2"
                />
              </div>

              <ul className="mt-3 divide-y hair-soft rounded-lg border hair bg-canvas">
                {visibleLocations.map((l) => (
                  <li key={l.id} className="flex items-center gap-3 px-4 py-3">
                    <span className={`h-1.5 w-1.5 rounded-pill ${l.accessible ? "bg-semantic-success" : "bg-stone"}`} />
                    <span className="text-body-sm text-ink">{l.name}</span>
                    <span className={`ml-auto text-caption-up uppercase ${l.accessible ? "text-brand-green" : "text-stone"}`}>
                      {l.accessible ? t("tracker.list.accessible") : t("tracker.list.not_accessible")}
                    </span>
                  </li>
                ))}
                {visibleLocations.length === 0 && (
                  <li className="px-4 py-8 text-center text-body-sm text-stone">{t("tracker.empty")}</li>
                )}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-caption text-steel uppercase tracking-[0.06em]">{label}</div>
      <div className="text-title-sm text-ink tabular-nums">{value}</div>
    </div>
  );
}

function isYamlFile(file: File): boolean {
  return /\.ya?ml$/i.test(file.name);
}

function YamlDropzone({
  file,
  onFile,
  disabled,
}: {
  file: File | null;
  onFile: (f: File | null) => void;
  disabled: boolean;
}) {
  const { t } = useT();
  const [dragOver, setDragOver] = useState(false);
  const [dropError, setDropError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  function accept(candidate: File | undefined | null) {
    if (!candidate) return;
    if (!isYamlFile(candidate)) {
      setDropError(t("tracker.yaml.wrong_type"));
      return;
    }
    setDropError(null);
    onFile(candidate);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    accept(e.dataTransfer.files?.[0]);
  }

  function onDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (!disabled) setDragOver(true);
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!disabled && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={onDragOver}
        onDragEnter={onDragOver}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragOver(false);
        }}
        onDrop={onDrop}
        aria-disabled={disabled}
        className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors duration-150 ${
          disabled
            ? "cursor-not-allowed border-hairline-strong bg-surface opacity-60"
            : dragOver
              ? "cursor-pointer border-primary bg-card-sky/40"
              : "cursor-pointer border-hairline-strong bg-surface hover:border-primary"
        }`}
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="text-steel">
          <path d="M12 16V4M12 4L7 9M12 4l5 5" />
          <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
        </svg>
        {file ? (
          <div className="flex items-center gap-2 text-body-sm text-ink">
            <span className="font-medium">{file.name}</span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setDropError(null);
                onFile(null);
              }}
              aria-label={t("tracker.yaml.remove")}
              className="text-steel hover:text-semantic-error"
            >
              ✕
            </button>
          </div>
        ) : (
          <>
            <div className="text-body-sm text-ink">
              {dragOver ? t("tracker.yaml.dropzone.active") : t("tracker.yaml.dropzone.idle")}
            </div>
            <div className="text-caption text-stone">{t("tracker.yaml.dropzone.hint")}</div>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".yaml,.yml"
          disabled={disabled}
          onChange={(e) => accept(e.target.files?.[0])}
          className="hidden"
        />
      </div>
      {dropError && <div className="mt-2 text-caption text-semantic-error">{dropError}</div>}
    </div>
  );
}
