"""Mix narration, ducked music and soft SFX into mix.m4a, then mux with video.mp4.

Music: bundled /brag tracks (ende.app "Happy Beats / Business Moves"),
chained with crossfades. SFX: Kenney soft impacts on scene changes and a warm
bong on each round-winner reveal, sitting under the music.
"""
import json
import pathlib
import subprocess
import sys

import imageio_ffmpeg

HERE = pathlib.Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
BRAG = pathlib.Path("/home/user/latent-spaces/brag/skills/brag/assets")
MUSIC = [("vol-1", 163.9), ("vol-12", 118.0), ("vol-9", 114.0), ("vol-11", 88.0), ("vol-10", 60.0)]
XF = 3.0  # music crossfade seconds


def main():
    tl = json.loads((HERE / "timeline.json").read_text())
    total = tl["total"]
    ins, fc, mixin = [], [], []

    # Music chain, long enough to cover the whole video.
    chain, length, k = [], 0.0, 0
    while length < total + 5:
        name, dur = MUSIC[k % len(MUSIC)]
        chain.append(BRAG / f"music/happy-beats-business-moves-{name}-by-ende-dot-app.mp3")
        length += dur - (XF if chain[1:] else 0)
        k += 1
    for m in chain:
        ins += ["-i", str(m)]
    prev = "[0:a]"
    for i in range(1, len(chain)):
        fc.append(f"{prev}[{i}:a]acrossfade=d={XF}:c1=tri:c2=tri[m{i}]")
        prev = f"[m{i}]"
    fc.append(f"{prev}atrim=0:{total:.3f},afade=t=in:d=1.5,afade=t=out:st={total - 4:.3f}:d=4,volume=0.24[music]")
    n = len(chain)

    # Narration, each scene placed at its voice start.
    voice = [s for s in tl["scenes"] if s.get("audio")]
    for s in voice:
        ins += ["-i", str(HERE / s["audio"])]
    for j, s in enumerate(voice):
        ms = int(s["voice_at"] * 1000)
        fc.append(f"[{n + j}:a]aresample=48000,adelay={ms}|{ms},apad=whole_dur={total:.3f}[v{j}]")
    n2 = n + len(voice)

    # SFX: scene changes + round-winner reveals.
    hits = []
    for i, s in enumerate(tl["scenes"]):
        if i:
            hits.append((s["start"] + 0.05, BRAG / f"sfx/impact/impactSoft_medium_00{i % 5}.ogg", 0.30))
        if s.get("round") and s["sentences"]:
            hits.append((s["start"] + s["sentences"][-1]["start"], BRAG / "sfx/interface/bong_001.ogg", 0.32))
    for _, f, _ in hits:
        ins += ["-i", str(f)]
    for j, (t, _, vol) in enumerate(hits):
        ms = int(t * 1000)
        fc.append(f"[{n2 + j}:a]aresample=48000,volume={vol},adelay={ms}|{ms}[x{j}]")
    fx = "".join(f"[x{j}]" for j in range(len(hits)))
    fc.append(f"{fx}amix=inputs={len(hits)}:normalize=0,lowpass=f=9000[sfx]")

    if voice:
        vv = "".join(f"[v{j}]" for j in range(len(voice)))
        fc.append(f"{vv}amix=inputs={len(voice)}:normalize=0,asplit=2[voice][key]")
        fc.append("[music][key]sidechaincompress=threshold=0.02:ratio=8:attack=30:release=600[duck]")
        fc.append("[duck][voice][sfx]amix=inputs=3:normalize=0:weights=1 1 1[pre]")
    else:
        fc.append("[music][sfx]amix=inputs=2:normalize=0[pre]")
    fc.append(f"[pre]atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[out]")

    subprocess.run([FF, "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fc),
                    "-map", "[out]", "-c:a", "aac", "-b:a", "192k", str(HERE / "mix.m4a")], check=True)
    print(f"mix.m4a: {total:.1f}s, {len(voice)} voice clips, {len(hits)} sfx, {n} music tracks")

    if "--mux" in sys.argv:
        out = HERE.parent / "brag.mp4"
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(HERE / "video.mp4"), "-i", str(HERE / "mix.m4a"),
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart",
                        "-shortest", str(out)], check=True)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
