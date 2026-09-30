#!/usr/bin/env bash
# Full build: narration -> timeline -> frames -> mix -> brag.mp4 + brag.jpg
#   ./build.sh            real Edge TTS voice (needs speech.platform.bing.com)
#   ./build.sh --estimate silent-voice preview timed from word counts
set -euo pipefail
cd "$(dirname "$0")"
FF=$(python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
python3 script.py
python3 tts.py ${1:-}
node capture.js video "${WORKERS:-4}"
python3 mix.py --mux
"$FF" -y -loglevel error -i ../brag.mp4 -frames:v 1 -q:v 2 ../brag.jpg
echo "done: $(cd .. && pwd)/brag.mp4"
