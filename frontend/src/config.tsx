import { ReactNode, createContext, useContext, useEffect, useMemo, useState } from "react";
import { SiteConfig, TagDef, api } from "./api";
import { Lang } from "./i18n";

// Fallback used before /api/config resolves and if the request fails. Mirrors
// the backend DEFAULTS in server/config.py so the UI is never blank.
export const DEFAULT_CONFIG: SiteConfig = {
  branding: {
    hero_title: "ArchipelaGoats",
    hero_image: "banner.png",
    hero_image_fade: 0.35,
    loading_name: "ArchipelaGoats",
  },
  footer: { left: "archipelago · nguengant.fr", right: "Have fun guys :)" },
  features: { hall_of_fame: true, death_leaderboard: true, constellation: true },
  hints: {
    blocked_tag: "bked",
    tags: [
      { id: "bked", label: "BKed", label_fr: "BKed", emoji: "🍔" },
      { id: "mandatory", label: "Mandatory", label_fr: "Obligatoire" },
      { id: "comfort", label: "Comfort", label_fr: "Confort" },
    ],
  },
};

function merge(base: SiteConfig, over: Partial<SiteConfig>): SiteConfig {
  return {
    branding: { ...base.branding, ...over.branding },
    footer: { ...base.footer, ...over.footer },
    features: { ...base.features, ...over.features },
    hints: {
      blocked_tag: over.hints?.blocked_tag ?? base.hints.blocked_tag,
      tags: over.hints?.tags ?? base.hints.tags,
    },
  };
}

type InjectedConfig = Partial<SiteConfig> & { basename?: string };

// Server-injected <script id="ap-config"> (see server/main.py); absent for self-hosted/demo.
let _injected: InjectedConfig | null | undefined;

function readInjectedConfig(): InjectedConfig | null {
  if (_injected !== undefined) return _injected;
  const el = document.getElementById("ap-config");
  try {
    _injected = el?.textContent ? (JSON.parse(el.textContent) as InjectedConfig) : null;
  } catch {
    _injected = null;
  }
  return _injected;
}

/** Site-relative base path for this room ("" at the root, "/<uuid>" when hosted), no trailing slash. */
export function getBasePath(): string {
  const basename = readInjectedConfig()?.basename;
  if (basename && basename !== "/") return basename.replace(/\/$/, "");
  return import.meta.env.BASE_URL.replace(/\/$/, "");
}

/** Resolve a branding image path to a URL usable from the current base. */

export function resolveAssetUrl(path: string): string {
  if (!path || /^(https?:)?\/\//.test(path) || path.startsWith("/")) return path;
  return getBasePath() + "/" + path;
}

/** Localized label for a tag definition. */
export function tagLabel(tag: TagDef, lang: Lang): string {
  return (lang === "fr" && tag.label_fr) || tag.label || tag.id;
}

const Context = createContext<SiteConfig | null>(null);

export function ConfigProvider({ children }: { children: ReactNode }) {
  const injected = readInjectedConfig();
  const [config, setConfig] = useState<SiteConfig>(
    injected ? merge(DEFAULT_CONFIG, injected) : DEFAULT_CONFIG,
  );

  useEffect(() => {
    if (injected) return; // hosted rooms already have everything from the tag
    let alive = true;
    api
      .config()
      .then((c) => alive && setConfig(merge(DEFAULT_CONFIG, c)))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [injected]);

  return <Context.Provider value={config}>{children}</Context.Provider>;
}

export function useConfig(): SiteConfig {
  const ctx = useContext(Context);
  if (!ctx) throw new Error("useConfig must be used inside <ConfigProvider>");
  return ctx;
}

/** Look up a single tag definition by id. */
export function useTagDef(id: string): TagDef | undefined {
  const cfg = useConfig();
  return useMemo(() => cfg.hints.tags.find((t) => t.id === id), [cfg, id]);
}
