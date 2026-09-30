"""Generate narration with Edge TTS (en-US-AndrewNeural) and build timeline.json.

Each scene gets audio/<id>.mp3 plus sentence timings. If the TTS service is
unreachable, pass --estimate to build the timeline from word counts instead
(silent preview; no audio files are written).
"""
import asyncio
import json
import os
import pathlib
import re
import subprocess
import sys

import edge_tts
import imageio_ffmpeg

HERE = pathlib.Path(__file__).parent
VOICE = "en-US-AndrewNeural"
RATE = "+4%"
LEAD_IN = 0.6   # silence before narration starts in each scene
TAIL = 1.0      # hold after narration ends
INTRO_LEAD = 2.4  # title hook plays before the first words
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]


def probe_duration(path):
    out = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


async def synth(scene, out_mp3):
    comm = edge_tts.Communicate(scene["text"], VOICE, rate=RATE, boundary="SentenceBoundary",
                                proxy=os.environ.get("HTTPS_PROXY"))
    sentences = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                start = chunk["offset"] / 1e7
                sentences.append(dict(start=start, end=start + chunk["duration"] / 1e7,
                                      text=chunk["text"]))
    return sentences, probe_duration(out_mp3)


def estimate(scene):
    t, sentences = 0.0, []
    for s in split_sentences(scene["text"]):
        d = len(s.split()) / 2.75 + 0.35
        sentences.append(dict(start=t, end=t + d - 0.35, text=s))
        t += d
    return sentences, t


async def main(use_estimate):
    scenes = json.loads((HERE / "scenes.json").read_text())
    (HERE / "audio").mkdir(exist_ok=True)
    t, timeline = 0.0, []
    for i, sc in enumerate(scenes):
        mp3 = HERE / "audio" / f"{i:02d}-{sc['id']}.mp3"
        if use_estimate:
            sentences, adur = estimate(sc)
        else:
            sentences, adur = await synth(sc, mp3)
            print(f"{sc['id']:<11} {adur:6.1f}s  {len(sentences)} sentences")
        lead = INTRO_LEAD if i == 0 else LEAD_IN
        dur = lead + adur + TAIL
        for s in sentences:
            s["start"] += lead
            s["end"] += lead
        timeline.append(dict(sc, start=t, dur=dur, voice_at=t + lead,
                             audio=None if use_estimate else str(mp3.relative_to(HERE)),
                             sentences=sentences))
        t += dur
    (HERE / "timeline.json").write_text(json.dumps(
        dict(total=t, estimated=use_estimate, scenes=timeline), indent=1))
    print(f"total {t:.1f}s ({t / 60:.2f} min){' [ESTIMATED]' if use_estimate else ''}")


if __name__ == "__main__":
    asyncio.run(main("--estimate" in sys.argv))
