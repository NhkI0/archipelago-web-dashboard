import type { SiteConfig } from "./api";

type InjectedConfig = Partial<SiteConfig> & { basename?: string };

// Server-injected <script id="ap-config"> (see server/main.py); absent for self-hosted/demo.
let _injected: InjectedConfig | null | undefined;

export function readInjectedConfig(): InjectedConfig | null {
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
