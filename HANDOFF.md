# Handoff: AI long-form YouTube video pipeline

> For Claude Code. Put this file in the root of the fork and read it before doing anything.

## Goal
Build a free, local pipeline on macOS that turns a researched topic into a **10–15 minute, 16:9 narrated explainer video**. The target is a monetized YouTube channel. Base it on a fork of [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) (MIT) and don't rewrite what already works.

## Owner and machine
- MacBook **M5 Pro, 48GB unified RAM**, Apple Silicon only (no CUDA). Based in Canada.
- Comfortable with Python and the command line. Wants brief, direct communication. **Ask clarifying questions before large changes.**
- Budget: prefers free. Small spend is OK for occasional rented GPUs or paid "hero" shots.

## Decisions already made
- **Long-form first** (8–15 min, 16:9). Cut Shorts from each long video later as trailers.
- **Fork MoneyPrinterTurbo** rather than build from scratch. Keep its TTS, subtitle and FFmpeg/MoviePy render modules.
- **The niche is not decided yet.** Leaning toward history, science or documentary explainers. Phase 1 helps choose.

## Why the design matters (YouTube policy)
YouTube demonetizes, and in 2026 has terminated, channels posting "mass-produced, generic, repetitive" or "templated" AI content. The pipeline must therefore:
1. Start from **research notes and a script the human edits**, not a one-click prompt.
2. **Match visuals sentence by sentence**, not by keyword montage (MoneyPrinterTurbo's main weakness).
3. Include a **human review step** before rendering.
4. **Never auto-upload.** Uploading stays manual so the human can tick YouTube's "altered or synthetic content" box when needed.

## Target architecture
```
research.md          human sources and notes
  → script.md        LLM draft → human edits
  → shots.json       per sentence: {text, visual_type: still|clip|stock, prompt, stock_query, duration}
  → review UI        Streamlit or Gradio: approve, edit or regenerate each shot   ← human checkpoint
  → audio/           Kokoro (default) or Chatterbox, per scene → timings
  → visuals/         FLUX still + Ken Burns | LTX clip (hero shots) | Pexels clip
  → captions.srt     from TTS timings or faster-whisper
  → render.mp4       16:9 long-form with chapters (+ later: 9:16 Shorts cut)
```
Build the new pieces (`shots.json` stage, review UI, long-form assembler, visual routing) as modules next to the existing code so upstream updates can still be merged.

## Stack (all free, commercial use allowed)
| Layer | Use | Notes |
|---|---|---|
| Script / shot list | **Claude via the owner's subscription only. No pay-per-use API, and no API keys.** Primary route: the owner writes `script.md` and `shots.json` interactively with Claude Code (subscription), and the pipeline reads those files. Also check MoneyPrinterTurbo's Claude Code option (it may run on the subscription). **Ollama** local model (8–32B fits in 48GB) is the automated fallback. | Never add Anthropic API billing |
| Voice | **Kokoro-82M** via mlx-audio; Chatterbox as the expressive option | Apache-2.0 / MIT |
| Stills | **mflux** (FLUX.1-schnell or FLUX.2 klein) | Check the model card license before use |
| Video clips | **mlx-video** or Draw Things: LTX-2.3/2.5 distilled, Wan 2.2 5B GGUF | Slow: estimated 3–5 min per 5 s clip. Use only for hero shots. |
| Stock | Pexels API (free key) | Free for commercial use |
| Assembly | FFmpeg, MoviePy, faster-whisper | Already in MoneyPrinterTurbo |

**Do not use:** XTTS v2, F5-TTS or Fish Speech (non-commercial licenses); FLUX.1-dev weights (non-commercial); FP8 checkpoints (fail on Apple's Metal, so use GGUF or distilled versions); Edge TTS as a required dependency (unofficial endpoint); MoneyPrinterV2 code (AGPL).

## Phases
**Phase 1: set up and assess (do this first)**
- Check prerequisites: Homebrew, Git, Python 3.11+, uv, FFmpeg, Ollama (fallback). List anything missing and ask before installing.
- Clone the owner's fork: https://github.com/mohamedbecha/MoneyPrinterTurbo. Add `upstream` pointing at https://github.com/harry0703/MoneyPrinterTurbo.
- Find out how MoneyPrinterTurbo's Claude Code option (added in v1.3.7) works: does it use the owner's Claude subscription or need an API key? If it needs an API key, don't use it.
- Make sure the pipeline can take a hand-made `script.md` (and later `shots.json`) as input instead of generating the script itself.
- Install it and run it unchanged with Ollama, Pexels and Kokoro. Make 2–3 test videos in 16:9 on candidate niche topics.
- Write `docs/assessment.md` covering: how the pipeline is structured (the key files and modules), where script → keywords → clips happens, how long videos can currently get, and what breaks on longer scripts.
- **Done when** the owner has watched the test videos and picked a niche.

**Phase 2: shot-level visuals**
- Add the `shots.json` stage and per-shot routing (still, clip or stock). Integrate mflux and mlx-video.
- **Done when** a 3-minute video has visuals matched sentence by sentence.

**Phase 3: long-form and review**
- Add the 8–15 minute 16:9 mode with chapters, the review UI and a consistent voice and style preset.
- **Done when** a 10-minute render is good enough that the owner would watch it.

**Phase 4 (later):** automatic 9:16 Shorts cuts, pacing and hook improvements, and an optional rented-GPU (RunPod/Vast, about $0.30–1/hr) backend for batches of clips.

## Working rules
- Commit in small steps with clear messages on feature branches. Keep `main` mergeable with upstream.
- Put API keys in `.env` or config and never commit them.
- Prefer fixes that run on the Mac. If something needs NVIDIA, say so rather than working around it silently.
- After each phase, give a short summary: what changed, how to run it, and what's next.
