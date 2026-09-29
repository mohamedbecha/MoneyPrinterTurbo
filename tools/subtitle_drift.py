# Compare estimated SRT cue starts vs faster-whisper word timings.
import re, sys, json
from faster_whisper import WhisperModel
d = sys.argv[1]
cues = []
for block in open(f"{d}/subtitle.srt", encoding="utf-8").read().strip().split("\n\n"):
    lines = block.splitlines()
    h, m, s = re.match(r"(\d+):(\d+):([\d,]+)", lines[1]).groups()
    cues.append((int(h)*3600+int(m)*60+float(s.replace(",", ".")), " ".join(lines[2:])))
model = WhisperModel("small.en", device="cpu", compute_type="int8")
segs, _ = model.transcribe(f"{d}/audio.mp3", word_timestamps=True)
words = [(w.start, re.sub(r"\W", "", w.word.lower())) for s in segs for w in s.words]
norm = lambda t: [re.sub(r"\W", "", x.lower()) for x in t.split()]
wi, errs = 0, []
for start, text in cues:
    first = norm(text)[:3]
    for j in range(wi, min(wi + 80, len(words) - 2)):
        if [w for _, w in words[j:j+3]] == first:
            errs.append((start, start - words[j][0])); wi = j + 1; break
abs_e = sorted(abs(e) for _, e in errs)
print(json.dumps({"cues": len(cues), "matched": len(errs),
  "median_abs_s": round(abs_e[len(abs_e)//2], 2), "p90_abs_s": round(abs_e[int(len(abs_e)*.9)], 2),
  "max_abs_s": round(abs_e[-1], 2),
  "by_minute": {int(t//60): round(e, 2) for t, e in errs[::max(1, len(errs)//12)]}}))
