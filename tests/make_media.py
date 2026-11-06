"""Generate the sample media used by the tests (needs ffmpeg with libopus).
Usage: python3 tests/make_media.py <output_dir>"""
import os
import subprocess
import sys

d = sys.argv[1]
os.makedirs(d, exist_ok=True)


def run(*a):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a], check=True)


run("-f", "lavfi", "-i", "sine=frequency=300:duration=10", "-ac", "1", "-c:a", "libopus", "-b:a", "16k", f"{d}/vo10.ogg")
run("-f", "lavfi", "-i", "sine=frequency=300:duration=130", "-ac", "1", "-c:a", "libopus", "-b:a", "16k", f"{d}/vo130.ogg")
run("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=1", "-frames:v", "1", f"{d}/foto.jpg")
run("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25", "-t", "3", f"{d}/vid.mp4")
with open(f"{d}/small.bin", "wb") as f:
    f.write(os.urandom(5000))
