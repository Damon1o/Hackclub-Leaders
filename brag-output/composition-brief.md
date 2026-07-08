# Hyperframes Composition Brief: Hack Club Leaders

## Objective
Create a short, ~19s launch-style brag video for **Hack Club Leaders** — the "Club HQ" dashboard teen leaders use to run their Hack Club.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: ~19 seconds

## Source Material
- Project root: `C:/Users/damon/Downloads/Coding Projects/Hackclub Leaders`
- Primary files read: `templates/index.html`, `templates/dashboard.html`, `templates/dashboard_layout.html`, `templates/dashboard/settings.html`, `static/css/base.css`, `static/css/hero.css`, `shop.json`, `README.md`
- Product name: Hack Club Leaders
- Tagline / strongest claim: "Where leaders build the future!" / "Everything you need to run your Hack Club."
- Key UI or visual moment to recreate: the **Club HQ dashboard** — the "Club HQ" eyebrow + club-name header, the four colored stat stickers (members / events planned / RSVPs in / projects shipped), and the club-level progress band. Plus the hero line with the animated gradient on "leaders."
- Copy that must appear verbatim:
  - "Where leaders build the future!"
  - "Club HQ"
  - "members strong" / "events planned" / "RSVPs in" / "projects shipped"
  - "Club level" / "Level 3"
  - "Everything you need to run your club."

## Creative Direction
- Tone preset: default
- Creative direction: colorful "Club HQ" dashboard reveal with authentic Hack Club energy
- Interpretation: comfortable 4-5 scene rhythm, warm first-person voice, vibrant multi-color motion, each stat given room to pop — playful but clean, never chaotic.
- Angle: This is the real Club HQ a teen leader opens to run their Hack Club, not a fake startup. Lean into Hack Club's loud, joyful brand — the red→orange gradient, the sticker aesthetic. Premise: one sign-in, and your entire club lights up in front of you. Every number and section is pulled straight from the app.
- Hook: "Where leaders build the future!" slams in on Hack Club red, "leaders" carrying the animated multi-color gradient.
- Outro / punchline: logo + "Everything you need to run your club."
- Avoid:
  - Generic SaaS language ("streamline your workflow")
  - Abstract filler visuals / particle systems
  - Unrelated visual redesign — stay true to the app's real look

## Visual Identity
- Background: `#ffffff` (light) — may use `#1f1f27` (Hack Club dark) for the hook stage
- Text: `#1a1a1a`
- Accent: `#ec3750` (Hack Club red); supporting `#ff8c37` orange, `#338eda` blue, `#33d6a6` green, `#a633d6` purple
- Display font: Zarathustra serif — bundled `static/fonts/zarathustra.otf` (copy into composition assets if used); otherwise a clean bold serif fallback
- Body font: Phantom Sans — fall back to a friendly geometric sans (system-ui / Inter feel)
- Visual references from the project: animated red→multicolor gradient text on "leaders"; sticker stat tiles (orange/blue/green/purple) with a big number + small label; club-level progress band with fill bar; roster bar split into leaders/members/mentors segments.

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Hook — 3s — "Where leaders build the future!" with animated gradient on "leaders," ambient red/orange/blue glow.
2. One sign-in → dashboard swoop — 3.5s — cursor clicks "Sign in with Hack Club"; Club HQ dashboard shell swoops in. Caption "One sign-in. Your whole club."
3. Club HQ stat stickers count up — 5s — four colored stickers arrive one by one (~1.0s apart), numbers count up: 24 members strong, 8 events planned, 63 RSVPs in, 12 projects shipped. Hold full set ~1s.
4. Club level fills + roster bar — 3.5s — "Club level — Level 3", progress bar sweeps to ~75%, roster bar segments grow in.
5. Outro / logo — 3s — Hack Club Leaders wordmark on red→orange, "Everything you need to run your club." Music fades.

## Audio
- Audio role: warm upbeat corporate bed — happy, forward-moving "let's build" energy
- Audio arc: opens under the hook, punctuates the sign-in click and four sequential sticker pops on the beat, lifts through the level fill, settles on the logo with a gentle fade
- Music: `happy-beats-business-moves-vol-1-by-ende-dot-app.mp3` (bundled, ~120 BPM)
- Music treatment: start 0s at moderate volume, sit beneath text, fade out over the last ~0.8s of the outro
- Music cue guidance: bundled preset at `~/.claude/plugins/cache/brag/brag/0.1.0/skills/brag/assets/music/cues/happy-beats-business-moves-vol-1-by-ende-dot-app.music-cues.json` (also copy into composition assets). ~120 BPM, beat grid ~0.5s. Strong cues to consider: 17.02s, 18.52s, 20.02s. Use the 16–20s beat-grid window for sequential sticker reveals — snap each sticker to every OTHER beat (~1.0s apart) so each number reads while counting up. Or run `npx hyperframes beats` on the copied track. Timing hints only — readability wins.
- Audio-reactive treatment: subtle — let the hero red glow / dashboard presence breathe slightly with music energy; NO waveform bars, NO equalizer, NO note graphics. If ffmpeg extraction is unavailable, skip audio-reactive and note it (do not block).
- Audio-coupled moments:
  - Scene 2 sign-in — soft click on cursor press + gentle whoosh on dashboard swoop
  - Scene 3 stickers — one soft pop per sticker arrival + subtle count-up ticks (fire at same timestamp as each visual)
  - Scene 4 level — progress-fill sweep sound; small settle when it stops
  - Scene 5 logo — single soft settle, then music fade
- SFX selection guidance: use the skill's `sfx-analysis.md` at `~/.claude/plugins/cache/brag/brag/0.1.0/skills/brag/assets/sfx/`. Prefer low high-frequency-risk files for the repeated sticker pops. One sound per beat max — warm and postable, not a hype reel.
- Exact SFX choice: Hyperframes (you) choose filenames, timestamps, density, and volume based on the implemented animation.
- Audio files: copy the chosen music and any selected SFX into `brag-output/composition/assets/`.

## Hyperframes Instructions
Use the current `hyperframes-core` authoring contract and the CLI workflow. Prefer native HyperFrames conventions over anything in `/brag`.

Requirements:
- Show at least one real UI element from the app (the Club HQ stat stickers + level band are the centerpiece).
- Keep all text readable in the final render (respect the reading-time floor: short labels ~0.8s settled, the hook line longer).
- Keep the video within 15-25 seconds (~19s target).
- Include music + tasteful SFX (audio was NOT disabled).
- Treat `/brag` audio notes as guidance; choose exact SFX after the visual animation exists.
- Lock 1–3 major reveals to strong cues (±0.15s); snap sequential sticker reveals to consecutive every-other-beat timestamps (±0.10s). Mark them `// beat-locked` / `// beat-grid`.
- Prefer local assets for audio and runtime deps.
- Run `hyperframes lint` and `hyperframes validate` before render.

## Known blocker (for delivery)
Local render needs **FFmpeg + FFprobe** (not installed) and **Chrome Headless Shell** (`npx hyperframes browser ensure`). Build + lint + validate proceed regardless; render waits on FFmpeg.
