# <img src="./frontend/public/logo.svg" width="50"> Archipelago Web Dashboard

I love Archipelago, my friends too but they sometimes get scared of *"techy"* stuff, like commands in a terminal. 
So I made this web tracker, to keep hints ordered and easy to make. If just someone in your group hosts it either on their computer or a server all of you can access it.
<br>
I tried to make a version of it that's easy to use, complete and highly customizable and I think it turned out pretty well. 
You can check out the actual render on the [live demo](https://nhki0.github.io/archipelago-web-dashboard/).

### Hosted version
This repository is the self-hosted version, but if you rather use an already packaged and hosted one you can !
I just made it so there may have little glitches but please try it and give feedback :)
- https://ap-dashboard.online/

> If at any moment you happen to have questions, hit me up on discord (**@nhankio**), I'd be more than pleased to help you.

## What's in there:
### Main Dashboard
- Live check/location tracking per player slot, gets updated in real time over the AP server's own WebSocket.
- A constellation map that gives an overview of all slots and their hint connections *(can be toggled off)*.
- "BKed checks" panels, whenever an item is blocking you or someone else this appears so you can't miss it (made mainly for asyncs).
- Counter of DeathLink sent per player, will persist after restart.
- Details for each slot about the content of their game.

### Hints
A whole tab that can:
- Send hints (item or locations) if logged into the slot, based of the actual hint-cost of the server. 
- Tag hints, show others if what's already hinted is blocking, mandatory, comfort or just useless (useful for games with shops that auto hint their content).
- Sort/filter/search the hint list.

### Hall of Fame
Made for showing my friends memes and fanart and keeping a better trace of it (instead of a random discord group).
- You can just drop any image into ``hall-of-fame/`` and list them in ``entries.toml`` to make them appear.

### Host configuration
All this found in ``config.toml``:
- Branding: change the text in the dashboard.
- Footer left/right.
- Feature toggles: if you don't care about hall of fame, death leaderboard or constellation map you can really easily disable it (but please don't it would make me sad).
- You can also create fully custom tags if mine are boring.
- Local or remote AP server: auto-detects if ``host.yaml`` sits next to your ``.archipelago`` file, connects locally; otherwise falls back to the config of ``[server.remote]``, this also works with games hosted on the official website.
- It's also possible to change the banner how you want with a few options, it was first made for my picture so it isn't perfect for all, ask me and I'll try to add more customization here.

### Login
- Players have to log in as their slot name (+ password if needed), to send hints and tag them. You can see who's online on the website with a little green dot (just like discord presence).

### Translated
- Only available in English and French as it was when I first made it, might put others later but we all know only french people need a translation and that english is enough for anybody else.

### Drag and drop
- Once everything is setup you just have to drag and drop your ``.archipelago`` (and ``host.yaml`` if locally hosting) and run the starting script corresponding to your operating system to launch the dashboard.

## SETUP (step by step)
### 0. Prerequisites
If you don't have it installed yet on your device, [install npm and Node.js](https://nodejs.org/en/download).<br>
Same goes for Python (>= 3.11), [which can be found here](https://www.python.org/downloads/).
### 1. Clone the repo
```bash
git clone https://github.com/NhkI0/archipelago-web-dashboard.git
cd archipelago-web-dashboard
```

### 2. Build the frontend once

```bash
cd frontend
npm install
npm run build
cd ..
```
---
**All the steps done before were one time only, once it's done you just need to pick-up the path A or B depending of your configuration.**

### 3. Fit it to your config
#### A. The archipelago server is running locally
1. Generate your multiworld as usual, get a ``*.archipelago`` file and the exact ``host.yaml`` that's used with the server.
2. Drop both into ``multiworld/``.
3. Check ``config.toml``'s ``[server].ap_host/ap_port`` match your local Archipelago server (the default values ``localhost:38281`` are right if it's the same machine).
4. Start your archipelago server separately.
5. Run ``run.bat`` (Windows) or ``run.sh`` (macOS/Linux).
6. Open ``http://localhost:8080``.

#### B. The archipelago server is running elsewhere
1. Get the exact ``.archipelago`` file matching the room you're watching.
2. Drop it into ``multiworld/`` without any ``host.yaml``.
3. Edit ``[server.remote]`` in ``config.toml`` (``host``, ``port``, ``password``, make sure ``tls = true`` for public rooms like [archipelago.gg](https://archipelago.gg/)).
4. Run ``run.bat`` (Windows) or ``run.sh`` (macOS/Linux). 
5. Open ``http://localhost:8080``.

<br>

> **How live tracking works (A & B):** instead of one websocket per player slot, the
> dashboard now holds a single placeholder connection that already sees everyone's checks,
> hints, and goal completions live. The moment anyone logs into the dashboard, that
> login takes over the job and the placeholder disconnects; when they log out, duty
> passes to another logged-in player if one's still around, or the placeholder comes
> back. The one thing that isn't instant for other slots: hint points, which refresh
> every ~10 minutes instead of live (the logged-in/placeholder slot's own hint points
> stay live throughout).

> **Picking the placeholder slot:** ``[server].default_slot`` names which slot the
> placeholder connects as. Leave it blank and it picks automatically (a slot that's
> already goaled and has DeathLink, else any DeathLink slot, else just the first one).
> If you name a slot yourself and it has no DeathLink enabled, DeathLink simply won't
> be tracked so pick a DeathLink-enabled slot if you want both or simply make people
> with deathlink connect whenever they play.

##### B2. The room is hosted on archipelago.gg
Instead of step 3 above, set ``[server.remote].room_url`` to the room's full URL
(e.g. ``https://archipelago.gg/room/AbCdEfGhIjKl``) and leave ``host``/``port`` blank.
The dashboard then polls archipelago.gg's public tracker API instead of opening one
websocket per player slot, which scales much better for big multiworlds.
> **Known limitation:** hint points shown are an estimate (checks × points - hints spent
> through this dashboard), since that public API has no way to tell a paid hint from a
> free one. It's exact as long as every hint for the room is requested from this
> dashboard; a hint redeemed from a player's own game client or another tool won't be
> counted and will make the shown balance read too high.

> **Update delay:** with nobody logged into this dashboard, checks/hints/goal status can
> take up to ~75 seconds to show up as archipelago.gg caches its tracker API for 60s, and
> the dashboard polls it every 15s on top of that. As soon as anyone logs in, checks,
> received items, and goal completions become instant for everyone over that one
> connection, not just the logged-in player's own slot. Hints stay instant only for
> the logged-in slot's own hints (as finder or receiver); other players' hints still
> follow the poll cycle.

> **DeathLink:** only tracked while someone with DeathLink enabled is logged
> into *this dashboard* (not their AP game client). Log out and tracking
> pauses until a DeathLink slot logs back in, any one of them is enough to catch all deaths for everyone.

### Open it to others
Now seek on the internet how to make a local website accessible outside your network, you'll find many tutorials (or AIs) that will explain it way better than I could.