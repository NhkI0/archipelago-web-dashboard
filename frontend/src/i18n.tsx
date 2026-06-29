import { ReactNode, createContext, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "en" | "fr";

type Dict = Record<string, string>;

const en: Dict = {
  // Top nav
  "nav.dashboard": "Dashboard",
  "nav.hints": "Hint manager",
  "nav.hof": "Hall of Fame",
  "nav.signin": "Sign in",
  "nav.signout": "Sign out",
  "nav.slot": "slot",
  "nav.hint_pts": "hint points",
  "nav.brand": "Archipelago",

  // Hero
  "hero.kicker": "Multiworld",
  "hero.intro": "Live progression for every slot in this world. Sign in as your slot to spend hint points without leaving the browser.",
  "hero.pane.world": "world.summary",
  "hero.pane.checks": "checks.global",
  "hero.pane.hints": "hints.in_flight",
  "hero.pane.server": "server.status",
  "hero.field.seed": "seed",
  "hero.field.slots": "slots",
  "hero.field.progress": "progress",
  "hero.field.checked_total": "checked / total",
  "hero.field.open": "open",
  "hero.field.found": "found",
  "hero.field.latest": "latest",
  "hero.field.running": "● running",
  "hero.field.port": "port 38281",
  "hero.field.tracker": "tracker · live ws",

  // Dashboard
  "dash.kicker": "Slots",
  "dash.title": "Player progression",
  "dash.active_n": "{n} active",
  "constellation.kicker": "Multiworld map",
  "constellation.title": "A constellation of {n} players",
  "constellation.intro": "Each avatar is a player; each thread is an item that has been hinted between two of their worlds.",
  "constellation.field.game": "game",
  "constellation.hover_hint": "Hover a player to highlight their hint threads · click to open the detail page.",
  "deaths.kicker": "Death leaderboard",
  "deaths.title": "Most spectacular failures",
  "deaths.contenders": "{n} contender{plural}",

  // Slot card / detail
  "slot.online": "online",
  "slot.offline": "offline",
  "slot.goal": "Goal",
  "slot.remaining": "remaining",
  "slot.hint_pts": "hint pts",
  "slot.hints": "hints",
  "slot.progress": "progress",
  "slot.checks": "checks",
  "slot.open_hints": "open hints",
  "slot.back": "← back",
  "slot.search_locations": "Search locations…",
  "slot.tab.all": "All",
  "slot.tab.remaining": "Remaining",
  "slot.tab.checked": "Checked",
  "slot.tab.hinted": "Hinted",
  "slot.no_locations": "No locations.",
  "slot.hints_panel.title": "Hints",
  "slot.hints_panel.sub": "Items the world has revealed for this slot.",
  "slot.hints_panel.empty": "None yet.",
  "slot.received_panel.title": "Items received",
  "slot.received_panel.sub": "Everything this slot has obtained, most recent first.",
  "slot.received_panel.empty": "Nothing received yet.",
  "slot.received.from": "from {sender} · {loc}",
  "slot.received.undated": "before tracking started",
  "slot.hint.you_find": "you find",
  "slot.hint.you_receive": "you receive",
  "slot.status.found": "found",
  "slot.status.open": "open",

  // Hints page
  "hints.kicker": "Hint manager",
  "hints.signin_title": "Sign in to hint",
  "hints.signin_body": "Hints cost your slot's hint points, so you need to be logged in as that slot.",
  "hints.tab.item": "Hint an item",
  "hints.tab.location": "Hint a location",
  "hints.tab.hints": "Hints",
  "hints.filter.placeholder": "Filter…",
  "hints.empty.locations": "No remaining locations to hint.",
  "hints.empty.items": "No items left to hint.",
  "hints.col.item": "Item",
  "hints.col.location": "Location",
  "hints.col.parties": "Finder → Receiver",
  "hints.col.status": "Status",
  "hints.empty.mine_for": "No hints for items you'll receive yet.",
  "hints.empty.mine_in": "No hints in your world yet.",
  "hints.empty.all": "No hints anywhere yet.",
  "hints.subtab.mine_for": "For my world",
  "hints.subtab.mine_in": "In my world",
  "hints.subtab.all": "All",
  "hints.toggle.hide_found": "Hide found",
  "hints.button.hint": "Hint",
  "hints.button.sending": "Sending…",
  "hints.confirm.title": "Confirm hint",
  "hints.confirm.body_item": "Hint item {target}?",
  "hints.confirm.body_location": "Hint location {target}?",
  "hints.confirm.cost": "cost",
  "hints.confirm.balance": "balance",
  "hints.confirm.after": "after",
  "hints.confirm.note": "Server hint cost is {pct}% of your total checks.",
  "hints.confirm.not_enough": "Not enough hint points.",
  "hints.confirm.cancel": "Cancel",
  "hints.confirm.confirm": "Confirm",

  // Login
  "login.kicker": "Sign in",
  "login.title": "Log in as your slot",
  "login.body": "Required to spend hint points from the browser. Sessions are scoped to this device only.",
  "login.field.slot": "Slot name",
  "login.field.password": "Password (if set)",
  "login.placeholder.slot": "e.g. dopamine",
  "login.placeholder.password": "optional",
  "login.error.default": "Login failed",
  "login.button.signin": "Sign in",
  "login.button.signing": "Signing in…",

  // Loading
  "common.loading": "Loading…",
  "common.lang.toggle": "FR",
  "common.theme.toggle_aria": "Toggle theme",

  // Hall of Fame
  "hof.kicker": "Hall of Fame",
  "hof.title": "Your masterclasses",
  "hof.intro": "Because I love yall and you are super funny and talented <3.",
  "hof.empty": "Nothing here yet.",
  "hof.by": "by",

  // Notifier
  "notify.hint_for_you": "Hint for you: {item} — in {finder}'s world ({loc})",

  // Footer
  "footer.left": "archipelago · nguengant.fr",
  "footer.right": "Have fun guys :)",
};

const fr: Dict = {
  "nav.dashboard": "Tableau de bord",
  "nav.hints": "Gestion d'indices",
  "nav.hof": "Panthéon",
  "nav.signin": "Connexion",
  "nav.signout": "Déconnexion",
  "nav.slot": "joueur",
  "nav.hint_pts": "points d'indice",
  "nav.brand": "Archipelago",

  "hero.kicker": "Multimonde",
  "hero.intro": "Progression en direct de chaque joueur. Connectez-vous avec votre slot pour dépenser vos points d'indice sans quitter le navigateur.",
  "hero.pane.world": "monde.resume",
  "hero.pane.checks": "checks.global",
  "hero.pane.hints": "indices.en_cours",
  "hero.pane.server": "serveur.statut",
  "hero.field.seed": "seed",
  "hero.field.slots": "joueurs",
  "hero.field.progress": "progression",
  "hero.field.checked_total": "validés / total",
  "hero.field.open": "ouverts",
  "hero.field.found": "trouvés",
  "hero.field.latest": "dernier",
  "hero.field.running": "● actif",
  "hero.field.port": "port 38281",
  "hero.field.tracker": "tracker · ws live",

  "dash.kicker": "Joueurs",
  "dash.title": "Progression des joueurs",
  "dash.active_n": "{n} actifs",
  "constellation.kicker": "Carte du multimonde",
  "constellation.title": "Une constellation de {n} joueurs",
  "constellation.intro": "Chaque avatar est un joueur ; chaque fil est un objet déjà indiqué entre deux de leurs mondes.",
  "constellation.field.game": "jeu",
  "constellation.hover_hint": "Survolez un joueur pour mettre en évidence ses indices · cliquez pour ouvrir sa page.",
  "deaths.kicker": "Classement des morts",
  "deaths.title": "Noobs Of All Time",
  "deaths.contenders": "{n} candidat{plural}",

  "slot.online": "en ligne",
  "slot.offline": "hors-ligne",
  "slot.goal": "Goal",
  "slot.remaining": "restants",
  "slot.hint_pts": "pts indice",
  "slot.hints": "indices",
  "slot.progress": "progression",
  "slot.checks": "checks",
  "slot.open_hints": "indices ouverts",
  "slot.back": "← retour",
  "slot.search_locations": "Chercher un emplacement…",
  "slot.tab.all": "Tous",
  "slot.tab.remaining": "Restants",
  "slot.tab.checked": "Validés",
  "slot.tab.hinted": "Indiqués",
  "slot.no_locations": "Aucun emplacement.",
  "slot.hints_panel.title": "Indices",
  "slot.hints_panel.sub": "Objets révélés pour ce joueur.",
  "slot.hints_panel.empty": "Aucun pour l'instant.",
  "slot.received_panel.title": "Objets reçus",
  "slot.received_panel.sub": "Tout ce que ce joueur a obtenu, du plus récent au plus ancien.",
  "slot.received_panel.empty": "Rien reçu pour l'instant.",
  "slot.received.from": "de {sender} · {loc}",
  "slot.received.undated": "avant le suivi",
  "slot.hint.you_find": "vous trouvez",
  "slot.hint.you_receive": "vous recevez",
  "slot.status.found": "trouvé",
  "slot.status.open": "ouvert",

  "hints.kicker": "Gestion d'indices",
  "hints.signin_title": "Connectez-vous pour utiliser les indices",
  "hints.signin_body": "Les indices coûtent les points de votre slot, vous devez donc être connecté avec ce slot.",
  "hints.tab.item": "Indiquer un objet",
  "hints.tab.location": "Indiquer un emplacement",
  "hints.tab.hints": "Indices",
  "hints.filter.placeholder": "Filtrer…",
  "hints.empty.locations": "Aucun emplacement restant à indiquer.",
  "hints.empty.items": "Aucun objet restant à indiquer.",
  "hints.col.item": "Objet",
  "hints.col.location": "Emplacement",
  "hints.col.parties": "Trouveur → Destinataire",
  "hints.col.status": "Statut",
  "hints.empty.mine_for": "Aucun indice pour les objets que vous recevrez.",
  "hints.empty.mine_in": "Aucun indice dans votre monde.",
  "hints.empty.all": "Aucun indice nulle part.",
  "hints.subtab.mine_for": "Pour mon monde",
  "hints.subtab.mine_in": "Dans mon monde",
  "hints.subtab.all": "Tous",
  "hints.toggle.hide_found": "Masquer les trouvés",
  "hints.button.hint": "Indice",
  "hints.button.sending": "Envoi…",
  "hints.confirm.title": "Confirmer l'indice",
  "hints.confirm.body_item": "Indiquer l'objet {target} ?",
  "hints.confirm.body_location": "Indiquer l'emplacement {target} ?",
  "hints.confirm.cost": "coût",
  "hints.confirm.balance": "solde",
  "hints.confirm.after": "après",
  "hints.confirm.note": "Le coût du serveur est {pct}% de vos checks totaux.",
  "hints.confirm.not_enough": "Points d'indice insuffisants.",
  "hints.confirm.cancel": "Annuler",
  "hints.confirm.confirm": "Confirmer",

  "login.kicker": "Connexion",
  "login.title": "Connectez-vous avec votre slot",
  "login.body": "Nécessaire pour dépenser des points d'indice depuis le navigateur. La session est limitée à cet appareil.",
  "login.field.slot": "Nom du slot",
  "login.field.password": "Mot de passe (si défini)",
  "login.placeholder.slot": "ex. dopamine",
  "login.placeholder.password": "facultatif",
  "login.error.default": "Échec de connexion",
  "login.button.signin": "Connexion",
  "login.button.signing": "Connexion…",

  "common.loading": "Chargement…",
  "common.lang.toggle": "EN",
  "common.theme.toggle_aria": "Changer le thème",

  // Hall of Fame
  "hof.kicker": "Panthéon",
  "hof.title": "Vos masterclass",
  "hof.intro": "Parceque je vous aime et que vous êtes super drôle et talentueux <3.",
  "hof.empty": "Rien à afficher pour l'instant.",
  "hof.by": "par",

  "notify.hint_for_you": "Indice pour vous : {item} — dans le monde de {finder} ({loc})",

  "footer.left": "archipelago · nguengant.fr",
  "footer.right": "Have fun la team :)",
};

const dictionaries: Record<Lang, Dict> = { en, fr };

type I18nCtx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

const Context = createContext<I18nCtx | null>(null);

function detectInitial(): Lang {
  if (typeof window === "undefined") return "en";
  const stored = window.localStorage.getItem("lang") as Lang | null;
  if (stored === "fr" || stored === "en") return stored;
  const nav = navigator.language?.toLowerCase() || "";
  return nav.startsWith("fr") ? "fr" : "en";
}

function format(template: string, vars?: Record<string, string | number>) {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? String(vars[k]) : `{${k}}`));
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectInitial);

  useEffect(() => {
    if (typeof document !== "undefined") document.documentElement.lang = lang;
    if (typeof window !== "undefined") window.localStorage.setItem("lang", lang);
  }, [lang]);

  const value = useMemo<I18nCtx>(
    () => ({
      lang,
      setLang: setLangState,
      t: (key, vars) => {
        const dict = dictionaries[lang];
        const tpl = dict[key] ?? dictionaries.en[key] ?? key;
        return format(tpl, vars);
      },
    }),
    [lang],
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useT() {
  const ctx = useContext(Context);
  if (!ctx) throw new Error("useT must be used inside <LanguageProvider>");
  return ctx;
}
