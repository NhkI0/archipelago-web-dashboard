// Per-game icons. Keyed by the exact game name from `slot_info.game`
// in the multidata. To add a new game, add it to its group, alphabetically.
//
// The optional PNG override path is `/games/<slug>.png`, drop a file
// into `frontend/public/games/` and `<GameIcon>` will pick it up.

export const GAME_EMOJI: Record<string, string> = {
  // Zelda
  "A Link Between Worlds": "🖼️",
  "A Link to the Past": "🗡️",
  "Link's Awakening DX": "🪺",
  "Majora's Mask Recompiled": "🎭",
  "Ocarina of Time": "🌳",
  "Ship of Harkinian": "🌳",
  "Skyward Sword": "🐦‍🔥",
  "The Legend of Zelda": "🛡️",
  "The Minish Cap": "🍃",
  "The Wind Waker": "⛵",
  "Twilight Princess": "🐺",
  "Zelda II": "🐲",

  // Mario & Cie
  "Mario Kart 64": "🏁",
  "Mario Kart Double Dash": "🛺",
  "Mario Kart Wii": "🏎️",
  "Mario Sports Mix": "🏐",
  "Paper Mario": "📰",
  "Paper Mario: The Thousand-Year Door": "🚪",
  "Paper Mario: TTYD": "📰",
  "Super Mario 64": "⭐",
  "Super Mario Bros": "🍄",
  "Super Mario Bros 3": "🍄",
  "Super Mario Galaxy": "🌌",
  "Super Mario Odyssey": "🎩",
  "Super Mario Sunshine": "☀️",
  "Super Mario World": "🍄",
  "Yoshi's Island": "🥚",
  "Luigi's Mansion": "🏚️",
  "Mario & Luigi Superstar Saga": "👬🏻",

  // Donkey Kong
  "Donkey Kong 64": "🦍",
  "Donkey Kong Country": "🦍",
  "Donkey Kong Country 3": "🦍",

  // Kirby
  "Kirby 64 - The Crystal Shards": "😮",
  "Kirby Super Star": "⭐",

  // Pikmin
  "Pikmin": "🌼",
  "Pikmin 2": "🪻",
  "Pikmin 3": "🌷",

  // Other Nintendo
  "Earthbound": "🏠",
  "Mother 3": "🏠",
  "Star Fox Adventures": "🦊",
  "Super Smash Bros. Melee": "🫯",
  "Super Smash Bros. Brawl - The Subspace Emissary": "🫯",

  // Pokémon
  "Pokemon Black and White": "🌇",
  "Pokemon Crystal": "💎",
  "Pokemon Emerald": "🌿",
  "Pokemon FireRed and LeafGreen": "🔥",
  "Pokemon HeartGold and SoulSilver": "🐦‍🔥",
  "Pokemon Mystery Dungeon": "🐾",
  "Pokemon Mystery Dungeon Explorers of Sky": "⚙️",
  "Pokemon Platinum": "🪞",
  "Pokemon Red and Blue": "🔴",
  "Pokemon Snap": "📷",
  "Pokemon Yellow": "⚡",

  // Metroid
  "AM2R": "🌐",
  "Metroid Fusion": "🧬",
  "Metroid Prime": "🔫",
  "Metroid Zero Mission": "👽",
  "Metroid: Zero Mission": "👽",
  "Super Metroid": "👽",

  // Castlevania
  "Aria of Sorrow": "🦇",
  "Castlevania 64": "🦇",
  "Castlevania: Circle of the Moon": "🌙",
  "Castlevania: Dawn of Sorrow": "🦇",
  "Symphony of the Night": "🦇",

  // Sonic
  "Sonic Adventure 2 Battle": "💨",
  "Sonic Adventure 2: Battle": "💨",
  "Sonic Adventure DX": "💨",
  "Sonic Battle": "🦔",
  "Sonic Heroes": "💨",
  "Sonic the Hedgehog": "💨",
  "Sonic the Hedgehog 2": "💨",

  // Mega Man
  "Mega Man 2": "🤖",
  "Mega Man Battle Network 3": "🧑‍💻",
  "Mega Man X": "🤖",
  "Mega Man X3": "🤖",

  // Final Fantasy
  "Final Fantasy": "🐦",
  "Final Fantasy Crystal Chronicles": "🏺",
  "Final Fantasy IV": "🌑",
  "Final Fantasy Mystic Quest": "⚔️",
  "Final Fantasy Tactics Advance": "🎯",
  "Final Fantasy V": "🐉",
  "Final Fantasy VI": "🪄",

  // Kingdom Hearts
  "Kingdom Hearts": "🗝️",
  "Kingdom Hearts 2": "🗝️",
  "Kingdom Hearts 3": "🗝️",
  "Kingdom Hearts III": "🗝️",
  "Kingdom Hearts Birth by Sleep": "🗝️",
  "Kingdom Hearts Dream Drop Distance": "🗝️",
  

  // Lego
  "Lego Star Wars: The Complete Saga": "🪐",
  "Lego Batman: The Video Game": "🦇",

  // Other RPGs
  "Chrono Trigger": "⏳",
  "Clair Obscur Expedition 33": "🥀",
  "Cyberpunk 2077": "🌆",
  "Dark Souls III": "⚔️",
  "Dark Souls Remastered": "🗡️",
  "DELTARUNE": "❤️",
  "Hylics 2": "🟣",
  "Lufia II": "🏰",
  "Monster Hunter World": "🐉",
  "Old School Runescape": "🪓",
  "Secret of Evermore": "🐶",
  "Secret of Mana": "🌳",
  "Undertale": "💀",

  // 2D platformers & metroidvanias
  "Blasphemous": "✝️",
  "Celeste": "🏔️",
  "Celeste (Open World)": "🏔️",
  "Cuphead": "🍵",
  "DLC Quest": "💸",
  "Hollow Knight": "🦋",
  "Hollow Knight: Silksong": "🪡",
  "Ori and the Blind Forest": "🌿",
  "Pizza Tower": "🍕",
  "The Messenger": "📜",
  "Timespinner": "⌛",

  // 3D platformers
  "A Hat in Time": "🎩",
  "Jak 3": "🥚",
  "Pseudoregalia": "🐐",
  "Ratchet and Clank 3": "🔧",
  "Spyro 2": "🐉",
  "The Grinch": "🎄",
  "Ty the Tasmanian Tiger": "🪃",

  // Action & adventure
  "Adventure": "🐉",
  "Ittle Dew 2": "🪓",
  "Mirror's Edge": "🌇",
  "TUNIC": "🦊",

  // Shooters
  "Black Ops 3 - Zombies": "🧟",
  "Borderlands 2": "🦄",
  "Deep Rock Galactic": "⛏️",
  "DOOM 1993": "👹",
  "DOOM II": "👹",
  "Heretic": "🪄",

  // Horror
  "Resident Evil 2 Remake": "🦝",
  "Shivers": "👻",
  "Signalis": "🟥",

  // Roguelikes & deckbuilders
  "Balatro": "🃏",
  "Hades": "🔱",
  "Hades2Rogue": "⚔️",
  "Inscryption": "🃏",
  "Risk of Rain 2": "☔",
  "Rogue Legacy": "🪙",
  "Slay the Spire": "🃏",
  "The Binding of Isaac Repentance": "💧",

  // Survival, crafting & sims
  "Don't Starve Together": "🪵",
  "Minecraft": "⛏️",
  "Oxygen Not Included": "❄️",
  "PEAK": "⛰️",
  "Powerwash Simulator": "🧽",
  "Raft": "🛟",
  "Satisfactory": "🏗️",
  "Slime Rancher": "💩",
  "Stardew Valley": "🌽",
  "Subnautica": "🤿",
  "Subnautica: Below Zero": "🧊",
  "Terraria": "⛏️",

  // Strategy
  "Age Of Mythology Retold": "⚡",
  "Bloons TD6": "🎈",
  "Civilization VI": "🏛️",
  "Plants vs. Zombies": "🧟",

  // Puzzle & exploration
  "Blue Prince": "👑",
  "Librarian Tidy Up the Arcane Library": "📚",
  "Lingo": "🔤",
  "Outer Wilds": "🪐",
  "Portal 2": "🎂",
  "The Witness": "🧩",

  // Racing & rhythm
  "Geometry Dash": "🔲",
  "Hatsune Miku Project Diva Mega Mix+": "🎤",
  "Trackmania": "🏎️",
  "YARGGuitarHero3": "🎸",

  // Minigames
  "Bumper Stickers": "🚗",
  "ChecksFinder": "✅",
  "Clique": "🔘",
  "Jigsaw": "🧩",
  "Paint": "🎨",
  "Wikipelago": "📑",
  "Yacht Dice": "🎲",
  "Carnival Games MiniGolf": "⛳",

  // Hell
  "League of Legends": "☣️",
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
