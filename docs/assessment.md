# Phase 1 assessment: MoneyPrinterTurbo v1.3.7 for long-form 16:9

Assessed on 2026-09-29 against upstream `d477832` (the fork was fast-forwarded to it). The machine is an M5 Pro with 48 GB. Everything marked *measured* comes from the three test renders below. Everything else was read from code, with file:line references.

## Setup that works

| Piece | Choice | Notes |
|---|---|---|
| Python | 3.11 via `uv` (`uv sync --python 3.11`) | System Python is 3.14, which is left alone |
| Tests | `uv run python -X utf8 -m pytest -q test` | Baseline: 1447 passed, 20 skipped |
| LLM (fallback) | Ollama `gpt-oss:20b` | `llm_provider = "ollama"`. A 4-paragraph script takes 10–24 s |
| LLM (primary) | Claude Code in this terminal writes `script.md`, and the file is passed in as `--video-script` | See "Claude Code provider" below |
| TTS | Kokoro-82M via [Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) (Apache-2.0) at `../kokoro-fastapi`, on MPS | 571 s of audio in 43 s, about **13× realtime** (*measured*) |
| Stock | **Pixabay**. Pexels has paused new API keys | `video_source = "pixabay"`, `pixabay_api_keys` in the gitignored `config.toml` |
| Render | FFmpeg 9 + MoviePy, `libx264` | 1920×1080, 30 fps |

Start Kokoro (it listens on localhost only):

```bash
cd ../kokoro-fastapi && USE_GPU=true DEVICE_TYPE=mps PYTORCH_ENABLE_MPS_FALLBACK=1 \
  PYTHONPATH=$PWD:$PWD/api MODEL_DIR=src/models VOICES_DIR=src/voices/v1_0 WEB_PLAYER_PATH=$PWD/web \
  uv run --no-sync uvicorn api.src.main:app --host 127.0.0.1 --port 8880
```

Render a hand-made script:

```bash
uv run python cli.py --video-aspect 16:9 --video-source pixabay --voice-name kokoro:af_heart \
  --match-materials-to-script --video-concat-mode sequential --video-count 1 \
  --video-subject "The Great Stink of 1858" --video-script "$(cat videos/great-stink/script.md)"
```

## How the pipeline is structured

There are three entrypoints, and all of them end up in `app/services/task.py:start` (1748), which calls `_run_pipeline` (1413):

- `webui/Main.py`: Streamlit.
- `main.py`: the FastAPI app at `app/asgi.py`. `POST /api/v1/videos` is defined in `app/controllers/v1/video.py`.
- `cli.py`: `run_cli` (1717) calls `build_video_params` (900).

The stages run in this order:

1. **Script.** `task.generate_script` (292) calls `llm.generate_script`. It is **skipped when `video_script` is non-empty** (task.py:294). So a hand-made script already works; no code change is needed.
2. **Search terms.** `task.generate_terms` (313) calls `llm.generate_terms`. This is 5 terms by default, or 8 "in narrative order" with `--match-materials-to-script`. It is skipped when `video_terms` is given.
3. **Audio.** `task.generate_audio` (482) calls `voice.tts` (1060). For Kokoro, `voice._openai_compatible_tts` (2323) sends **one POST with the whole script**, with a 120 s timeout.
4. **Subtitles.** `task.generate_subtitle` (580) builds cues from TTS word boundaries (Edge TTS only). For every other TTS it uses `voice.populate_legacy_submaker_with_full_text` (1156), which splits by punctuation and **spreads the duration across cues by character count**. It uses faster-whisper only if `subtitle_provider = "whisper"`, and there is no automatic fallback.
5. **Materials.** `task.get_video_materials` (648) calls `material.download_videos` (2002). With script-order matching on, it goes through `_download_videos_by_script_order` (2764), which takes one candidate per term per round.
6. **Render.** `video.combine_videos` (820) cuts each clip to `video_clip_duration` (default 5 s) and joins them with the FFmpeg concat demuxer. Then `video.generate_video` (1345) uses MoviePy to composite voice, subtitles (one `TextClip` per cue) and BGM, writing `storage/tasks/<id>/final-1.mp4`.

Other service modules:

- `material.py`, `material_cache.py`: stock search, with a 24 h cache.
- `llm.py`: about 30 LLM providers.
- `subtitle.py`: faster-whisper.
- `bgm.py`: background music.
- `state.py`: task state, in memory or Redis.
- `task_artifacts.py`: writes `script.json`.

**Where script → keywords → clips happens:** `llm.generate_terms` turns the *whole script* into 5–8 short search phrases (llm.py around 905). Each phrase becomes one stock query (`material.search_videos_pixabay`, around 441: `q=<term>`, `per_page=50`). The clips are then laid down in term order, 5 s at a time. **Nothing maps a sentence to a timestamp.** "Match to script" only means the terms are generated in narrative order.

### Claude Code provider (v1.3.7)
`llm.py:_generate_response`, in the `claude_code` branch (about 474–593), runs `claude -p --output-format json --tools "" --safe-mode [--model …]` in a temporary directory. It removes `ANTHROPIC_*` from the environment, so it **uses the logged-in CLI and your subscription, with no API key**. That is policy-compliant.

We still don't need it for the main route: the script is written interactively here and passed in. It is a good optional automated route for `generate_terms` (or, later, `shots.json`) if Ollama's quality is too low. Its limit is a 300 s timeout per call.

## Test renders (*measured*)

| Video | Script source | Audio | Wall time | Notes |
|---|---|---|---|---|
| Olbers' paradox (science) | Ollama, 4 paragraphs | 84 s | 3 m 36 s | 17 clips. Terms were all "night sky …" |
| Svalbard seed vault (documentary) | Ollama, 4 paragraphs | 109 s | 4 m 32 s | 22 clips. **No frame shows the vault** |
| Great Stink of 1858 (history) | Hand-made, 1,628 words | 571 s (9.5 min) | 26 m 28 s | 93 clips, footage ran out, 22 clips looped. Mostly birds, rivers and parks. Not one frame shows Victorian London |

Stage timings for the long run:

| Stage | Time |
|---|---|
| Terms (Ollama) | 16 s |
| Kokoro | 43 s |
| Pixabay search + download (93 clips) | 2 m 51 s |
| Clip cutting and concat | about 13.5 min |
| Final MoviePy composite | about 9 min (about 1× realtime) |

The total is about 2.8× realtime. Clip preparation is slower than the final composite.

Kokoro's `af_heart` voice reads at about **171 wpm**. That means 10 minutes is about 1,700 words and 15 minutes is about 2,550 words.

## What breaks, or degrades, as scripts get longer

In order of impact:

1. **Relevance of the visuals.** This is the main weakness, as the handoff predicted. 8 terms for a 10-minute script means each term covers about 70 s of narration. The LLM also prefixed every term with the subject ("Great Stink toilets", "Seed Vault partnerships"). Stock libraries have nothing literal for these, so they return loosely related B-roll: dandelions, DNA helixes, handshakes, a Christmas house in a science video. The Great Stink got songbirds, an orangutan, a Union Jack on a green screen, and what looks like Budapest's Parliament. History topics are hit worst because there is no stock footage of 1858.
2. **The clip pool runs out, and clips loop.** 8 terms produced only 93 usable Pixabay candidates (each must be exactly 1920×1080 and at least 5 s long). That gave 465 s of footage for 571 s of audio, so 22 clips were repeated (video.py:1068). A 15-minute script would repeat much more. Repeated footage is exactly the "repetitive" signal YouTube's policy targets.
3. **Subtitle sync.** Kokoro returns no word timings, so the cue times are estimated. Compared against faster-whisper (`small.en`) word timings on the 9.5-minute audio (175 of 199 cues matched), the drift was **1.7 s median, 5.1 s at p90, 6.7 s max**. It drifts back and forth over the run and never settles. That's unwatchable. The fix is to set `subtitle_provider = "whisper"` or to align cues to the audio per sentence.
4. **Render time.** The final composite builds every subtitle `TextClip` up front and composites frames in Python, at roughly 1× realtime on this machine, after a 13.5-minute clip cut and concat. During the composite, Python generating frames is capped at one core (about 95%) and x264 uses about 2 cores. Frame generation is the likely bottleneck, so switching the encoder alone may not help much. It does not load clips into RAM, because they are streamed from temp files. A 15-minute video would take about 40 minutes end to end. `video_codec = "h264_videotoolbox"` is supported in config and has not been measured yet.
5. **Subtitle readability.** White text with a thin stroke and no background disappears on bright frames such as sky or a yellow wall. Turn on `--subtitle-background-enabled` or use a lower-third box.
6. **Subtitle glyphs.** The default font renders the Unicode non-breaking hyphen (U+2011) as □, and curly apostrophes get a gap ("vault’ s"). Ollama emits both. Hand-made scripts are safe if they use ASCII punctuation, but the input should be normalised.
7. **Single-request TTS.** The 120 s timeout was *not* a problem: 9.5 minutes took 43 s. But there is one request for the whole script, and a failure redoes all of it. Per-scene TTS, which Phase 2 needs anyway for timings, removes this risk.
8. **No structure.** There are no chapters, no sections, no pacing changes, and no per-scene control. The script is one block of text.

Hard caps: `video_script` has **no length cap**. `paragraph_number` is limited to 1–10, but that only applies when the LLM writes the script. There is no task-level timeout. The FFmpeg concat timeout is 3600 s.

## Recommendations for Phase 2

- **Build an eval gate first.** It should be an executable check that runs on every render:
  - every sentence has a shot;
  - no clip is reused within N minutes;
  - subtitle drift p90 is under 0.3 s against Whisper;
  - A/V duration delta is under 0.2 s;
  - no missing glyphs.

  The drift script used here (`tools/subtitle_drift.py`) is the start of that.
- **Build `shots.json` per sentence** with explicit `stock_query` phrases that describe the *image* ("Victorian brick sewer tunnel", "murky river at low tide"), not the topic.
- **Do TTS per scene** to get exact scene timings. Use faster-whisper for word-level captions.
- **Treat stock as the weakest source for history.** Plan for FLUX stills with Ken Burns motion as the default for historical topics, with stock for generic B-roll.
- **Measure `h264_videotoolbox`** against `libx264` on the final composite.

## Open questions for the owner
- **Niche:** watch the three test videos (in `storage/tasks/*/final-1.mp4`) and pick one.
- **Voice:** `af_heart` (American) was used. For history or documentary, a British voice (`bf_emma`, `bm_george`) may suit better. This is worth an A/B test.
