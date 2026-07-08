# Brag Plan: Hack Club Leaders

## What is this app?
A Flask web portal where Hack Club club leaders sign in with their Hack Club identity and run their whole club from one colorful dashboard — roster, events + RSVPs, shipped projects, club-level progression, a swag/hardware shop, and newsletters.

## The angle
This isn't a fake startup — it's the real "Club HQ" a teen leader opens to run their Hack Club. The video leans into Hack Club's own loud, joyful brand: the red-to-orange gradient, the sticker aesthetic, the hand-drawn energy. The premise: *one sign-in, and your entire club lights up in front of you.* Specific because every number, sticker, and section is pulled straight from this app — "events planned," "RSVPs in," "projects shipped," "Level 3," the actual shop items.

## Hook (first 2-3 seconds)
The hero line slams in on Hack Club red: **"Where leaders build the future!"** — with "leaders" carrying the animated multi-color gradient, exactly like the live site. Ambient red/orange/blue blobs glow behind it. That gradient word is the recognizable Hack Club hook.

## Key moments (the middle)
- **The sign-in → dashboard swoop.** A "Sign in with Hack Club" button, a cursor click, and the Club HQ dashboard rushes in. One action, whole club revealed.
- **The four stat stickers arriving one by one and counting up** — 24 members strong, 8 events planned, 63 RSVPs in, 12 projects shipped — in Hack Club orange/blue/green/purple, each with a satisfying pop.
- **The club-level band filling** — "Level 3" with the progress bar sweeping toward the next perk, plus the roster bar split into leaders / members / mentors.

## Outro / punchline
Everything settles, the logo lands: **"Hack Club Leaders — everything you need to run your club."** Light, warm, postable.

## User flow worth showing
Real happy path pulled from the app: **Sign in with Hack Club → land on Club HQ → the stat stickers + club level populate → glance at the shop.** The centerpiece scenes ARE this flow (sign-in click, dashboard reveal, stat count-up, level fill), not the marketing sections.

## Tone
- Preset: default
- Creative direction: colorful "Club HQ" dashboard reveal with authentic Hack Club energy
- Interpretation: comfortable 4-5 scene rhythm, warm first-person voice, vibrant multi-color motion, each stat given room to pop — playful but clean, never chaotic.

## Format: landscape — 1920x1080
## Duration: ~19s

## Visual identity (from the project)
- Background: `#ffffff` (light) / `#1f1f27` dark (`--hackclub-dark`)
- Accent: `#ec3750` (Hack Club red) — supporting `#ff8c37` orange, `#338eda` blue, `#33d6a6` green, `#a633d6` purple
- Text: `#1a1a1a`
- Display font: Zarathustra (serif) — bundled at `static/fonts/zarathustra.otf`; if embedding is awkward, fall back to a clean bold serif
- Body font: Phantom Sans (Hack Club) — fall back to a friendly geometric sans (e.g. system UI / Inter feel)
- Strongest visual element: the animated red→multicolor gradient on "leaders," and the Club HQ sticker row (orange/blue/green/purple stat tiles) + the level progress band

## Share copy (draft)
Built a Club HQ for Hack Club leaders — sign in once and your whole club lights up: roster, events, ships, levels, shop. 🚩

## Audio direction
- Role: warm upbeat corporate bed — happy, forward-moving, "let's build something" energy
- Music: `happy-beats-business-moves-vol-1` (bundled, ~120 BPM). None only if `--no-music`.
- Music treatment: start at 0s under the hook at moderate volume, sit beneath text, gentle fade-out over the last ~0.8s of the outro.
- Music cue guidance: track ~120 BPM, beat grid every ~0.5s. Target strong cues at **17.02s, 18.52s, 20.02s** for punctuating the level fill / outro; use the 16–20s beat-grid window for the sequential sticker reveals (snap each sticker to every other beat, ~1.0s apart, so each number is readable as it counts up). Timing hints only — story and readability win.
- Audio-reactive treatment: subtle — let the hero red glow and dashboard presence breathe slightly with the music energy; no waveform bars.
- SFX posture: moderate, motion-matched — a soft click on the sign-in cursor press, a light pop per stat sticker arrival, a gentle whoosh on the dashboard swoop, one clean settle on the logo.
- Audio-coupled moments: cursor click (sign-in), four sequential sticker pops with count-up ticks, progress-bar fill sweep, logo settle.
- Restraint rule: no harsh stingers, no dubstep drops, no more than one sound per beat — keep it warm and postable, not a hype reel.

## Storyboard

### Scene 1 — Hook: "Where leaders build the future!" — 3s
White (or Hack Club dark) stage with soft ambient red/orange/blue blobs. The headline slams in fast and HOLDS; "leaders" carries the animated Hack Club gradient. Fast-in (~0.4s), settled hold ~2.4s so the full line reads.
Sequential/interaction: none
Audio intent: warm upbeat music opens; establishes joyful momentum
Audio-coupled idea: none (let music carry the open)
Music: happy-beats-business-moves-vol-1 from 0s
Transition mood: clean crossfade → Scene 2

### Scene 2 — One sign-in → dashboard swoop — 3.5s
A tidy "Sign in with Hack Club" button sits center on a card. A cursor glides in and clicks it; the Club HQ dashboard shell swoops in from the click (sidebar + "Club HQ / Your Club" header). Caption: **"One sign-in. Your whole club."** (hold ~1.3s).
Sequential/interaction: yes — simulate the cursor clicking the sign-in button, then the dashboard swooping in
Audio intent: a decisive click, then a satisfying reveal whoosh
Audio-coupled idea: soft click on press + gentle whoosh on the dashboard swoop
Music: continues, warm bed
Transition mood: clean wipe/whoosh → Scene 3

### Scene 3 — Club HQ stat stickers count up — 5s
The four colorful stat stickers arrive ONE BY ONE (~1.0s apart, aligned to the beat grid) and each number counts up: **24 members strong** (orange), **8 events planned** (blue... use orange/blue/green/purple order from app), **63 RSVPs in**, **12 projects shipped**. After the fourth lands, hold the full set ~1.0s so all four read.
Sequential/interaction: yes — 4 stickers appear one by one, each with a pop + count-up tick
Audio intent: each arrival feels earned; light, satisfying
Audio-coupled idea: one soft pop per sticker + subtle count-up ticks; snap arrivals to every-other-beat in the 16–20s window
Music: continues; reveals ride the beat
Transition mood: clean crossfade → Scene 4

### Scene 4 — Club level fills + roster bar — 3.5s
The level band takes the stage: **"Club level — Level 3"** with the progress-bar fill sweeping ~0→75% toward "next perk," and the roster bar splitting into leaders / members / mentors segments. Caption hold ~1.2s.
Sequential/interaction: yes — progress bar sweeps to fill; roster segments grow in
Audio intent: a rising, "leveling up" lift; land the fill on a strong cue (~18.5–20s)
Audio-coupled idea: progress-fill sweep sound; small settle when it stops
Music: continues, energy slightly up
Transition mood: clean crossfade → Scene 5

### Scene 5 — Outro / logo — 3s
Everything resolves to the Hack Club Leaders logo/wordmark on brand red-to-orange. Tagline: **"Everything you need to run your club."** Hold ~2s. Music fades out over the last ~0.8s.
Sequential/interaction: none
Audio intent: warm resolve; one clean settle, then fade
Audio-coupled idea: single soft logo settle
Music: final strong cue (~20s) then fade
Transition mood: soft settle → end

**Music mood for this video:** upbeat (warm corporate / happy-build energy)
**Audio summary:** A warm ~120 BPM happy bed opens on the hook, punctuates the sign-in click and the four sequential sticker pops on the beat, lifts through the level fill, and settles on the logo with a gentle fade — polished and postable, never a hype reel.
