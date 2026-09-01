// Per-game icons. Keyed by the exact game name from `slot_info.game`
// in the multidata. To add a new game, just append to GAME_EMOJI.
//
// The optional PNG override path is `/games/<slug>.png`, drop a file
// into `frontend/public/games/` and `<GameIcon>` will pick it up.

export const GAME_EMOJI: Record<string, string> = {

  // Zelda family
  "A Link to the Past": "🗡️",
  "Ocarina of Time": "🌳",
  "The Legend of Zelda": "🛡️",
  "Zelda II": "🐲",
  "Link's Awakening DX": "🪺",
  "The Minish Cap": "🍃",
  "Twilight Princess": "🐺",
  "A Link Between Worlds": "🖼️",
  "Skyward Sword": "🐦‍🔥",
  "Majora's Mask Recompiled": "🎭",
  "The Wind Waker": "⛵",

  // Mario / Yoshi family
  "Super Mario 64": "⭐",
  "Super Mario World": "🍄",
  "Super Mario Bros": "🍄",
  "Super Mario Bros 3": "🍄",
  "Super Mario Sunshine": "☀️",
  "Super Mario Odyssey": "🎩",
  "Super Mario Galaxy": "🌌",
  "Paper Mario": "📰",
  "Paper Mario: TTYD": "📰",
  "Yoshi's Island": "🥚",
  "Mario Kart 64": "🏁",

  // Pokémon
  "Pokemon Red and Blue": "🔴",
  "Pokemon Yellow": "⚡",
  "Pokemon Crystal": "💎",
  "Pokemon Emerald": "🌿",
  "Pokemon FireRed and LeafGreen": "🔥",
  "Pokemon Mystery Dungeon": "🐾",

  // Metroid / Castlevania
  "Super Metroid": "👽",
  "Metroid Zero Mission": "👽",
  "Metroid Prime": "🔫",
  "Metroid Fusion": "🧬",
  "AM2R": "🌐",
  "Castlevania 64": "🦇",
  "Castlevania: Circle of the Moon": "🌙",
  "Aria of Sorrow": "🦇",
  "Symphony of the Night": "🦇",
  "Blasphemous": "✝️",

  // Sonic
  "Sonic the Hedgehog": "💨",
  "Sonic the Hedgehog 2": "💨",
  "Sonic Adventure 2: Battle": "💨",
  "Sonic Adventure DX": "💨",
  "Sonic Heroes": "💨",
  "Sonic Battle": "🦔",

  // Final Fantasy / SquareEnix
  "Final Fantasy": "🐦",
  "Final Fantasy IV": "🌑",
  "Final Fantasy V": "🐉",
  "Final Fantasy VI": "🪄",
  "Final Fantasy Mystic Quest": "⚔️",
  "Final Fantasy Tactics Advance": "🎯",
  "Chrono Trigger": "⏳",
  "Secret of Mana": "🌳",
  "Secret of Evermore": "🐶",
  "Lufia II": "🏰",

  // Mega Man / Capcom
  "Mega Man Battle Network 3": "🧑‍💻",
  "Mega Man 2": "🤖",
  "Mega Man X": "🤖",
  "Mega Man X3": "🤖",

  // Indies & modern
  "Hollow Knight": "🦋",
  "Celeste": "🏔️",
  "Celeste (Open World)": "🏔️",
  "Stardew Valley": "🌽",
  "Terraria": "⛏️",
  "Minecraft": "⛏️",
  "Subnautica: Below Zero": "🧊",
  "Don't Starve Together": "🪵",
  "Risk of Rain 2": "☔",
  "Slay the Spire": "🃏",
  "Hades": "🔱",
  "Hade2Rogue": "⚔️",
  "Pizza Tower": "🍕",
  "Shivers": "👻",
  "The Witness": "🧩",
  "A Hat in Time": "🎩",
  "Earthbound": "🏠",
  "Mother 3": "🏠",
  "DLC Quest": "💸",
  "Donkey Kong Country": "🦍",
  "Donkey Kong Country 3": "🦍",
  "Bumper Stickers": "🚗",
  "Clique": "🔘",
  "ChecksFinder": "✅",
  "Raft": "🛟",
  "Outer Wilds": "🪐",
  "Inscryption": "🃏",
  "Balatro": "🃏",
  "Tunic": "🦊",
  "Lingo": "🔤",
  "Ittle Dew 2": "🪓",
  "Adventure": "🐉",
  "Yacht Dice": "🎲",
  "Hatsune Miku Project Diva Mega Mix+": "🎤",
  "Clair Obscur Expedition 33": "🥀",
  "Slime Rancher": "💩",
  "Undertale": "💀",
  "Monster Hunter World": "🐉",
  "DELTARUNE": "❤️",
  "The Binding of Isaac Repentance": "💧",

  // Doom / Retro shooters
  "DOOM 1993": "👹",
  "DOOM II": "👹",
  "Heretic": "🪄",

  // Nintendo
  "Kirby Super Star": "⭐",
  "Kirby 64 - The Crystal Shards": "😮",
  "Resident Evil 2 Remake": "🦝",
  "Kingdom Hearts": "🗝️",
  "Kingdom Hearts 2": "🗝️",
  "Kingdom Hearts 3": "🗝️",
  "Pokemon Snap": "📷",
  "Pikmin": "🌼",
  "Pikmin 2": "🪻",
  "Pikmin 3": "🌷",
  
  // Others
  "Dark Souls III": "⚔️",
  "Old School Runescape": "🪓",
  "Hylics 2": "🟣",
  "The Messenger": "📜",
  "Timespinner": "⌛",
  "Rogue Legacy": "🪙",
  "Portal 2": "🎂",
  "Trackmania": "🏎️",
  "Age Of Mythology Retold": "⚡",
  "Cuphead": "🍵",
  "Mario Sports Mix": "🏐",
  "Mirror's Edge": "🌇",
  "Paper Mario: The Thousand-Year Door": "🚪",
  "Satisfactory": "🏗️",
  "Subnautica": "🤿",
  "Ori and the Blind Forest": "🌿",
  "Oxygen Not Included": "❄️",
  "Civilization VI": "🏛️",
  "Black Ops 3 - Zombies": "🧟",
  "The Grinch": "🎄",
  "Jigsaw": "🧩",
};

const FALLBACK_EMOJI = "🎮";

/*
Examples:
slugify("Subnautica")                -> "subnautica"
slugify("A Link to the Past")        -> "a-link-to-the-past"
slugify("Majora's Mask Recompiled")  -> "majoras-mask-recompiled"
slugify("Pokemon Red and Blue")      -> "pokemon-red-and-blue"
slugify("Sonic Adventure 2: Battle") -> "sonic-adventure-2-battle"
slugify("DOOM 1993")                 -> "doom-1993"
slugify("Paper Mario: TTYD")         -> "paper-mario-ttyd"
slugify("Pokémon Crystal")           -> "pokemon-crystal"   (diacritic stripped)
slugify("  Hollow   Knight  ")       -> "hollow-knight"     (whitespace collapsed)
*/
export function slugify(game: string): string {
  return game
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export function gameMeta(game: string): { slug: string; emoji: string } {
  return {
    slug: slugify(game),
    emoji: GAME_EMOJI[game] ?? FALLBACK_EMOJI,
  };
}
