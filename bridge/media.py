"""Media transcoding between WhatsApp and LXMF.

Images: Sideband presets (low 320 px WebP q22, medium 640 px q66, high 1280 px q75).
Audio: raw Codec2 (the format Sideband puts in FIELD_AUDIO) or Opus/ogg,
via ffmpeg built with libcodec2 and libopus.

Levels are always the English canonical names: low, medium, high, original.
"""

import io
import os
import subprocess
import tempfile

from PIL import Image, ImageOps

# LXMF constants (LXMF/LXMF.py) repeated here so the tests need not import LXMF.
AM_CODEC2_700C = 0x03
AM_CODEC2_1200 = 0x04
AM_CODEC2_1300 = 0x05
AM_CODEC2_1400 = 0x06
AM_CODEC2_1600 = 0x07
AM_CODEC2_2400 = 0x08
AM_CODEC2_3200 = 0x09
AM_OPUS_OGG = 0x10

CODEC2_MODES = {
    AM_CODEC2_700C: ("700C", 700),
    AM_CODEC2_1200: ("1200", 1200),
    AM_CODEC2_1300: ("1300", 1300),
    AM_CODEC2_1400: ("1400", 1400),
    AM_CODEC2_1600: ("1600", 1600),
    AM_CODEC2_2400: ("2400", 2400),
    AM_CODEC2_3200: ("3200", 3200),
}
CODEC2_BY_NAME = {name: am for am, (name, _) in CODEC2_MODES.items()}


class MediaError(Exception):
    pass


def _ffmpeg(args, stdin=None):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"] + args
    p = subprocess.run(cmd, input=stdin, capture_output=True, timeout=120)
    if p.returncode != 0:
        raise MediaError(p.stderr.decode(errors="replace").strip()[-300:] or "ffmpeg failed")
    return p.stdout


# ------------------------------------------------------------------ immagini

def image_low(data, max_px=320, quality=22):
    """Any image -> low-quality WebP, like Sideband's "low" preset."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((max_px, max_px))
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
            buf = io.BytesIO()
            im.save(buf, format="webp", quality=quality, method=6)
            return buf.getvalue()
    except Exception as e:
        raise MediaError(f"unreadable image: {e}")


# Sideband presets (lbimg / defimg / hqimg): longest side and WebP quality
IMG_PRESETS = {"low": (320, 22), "medium": (640, 66), "high": (1280, 75)}


def image_for(data, level):
    """Image -> (LXMF type, bytes) at the requested level. 'original' = file unchanged."""
    if level == "original":
        try:
            with Image.open(io.BytesIO(data)) as im:
                fmt = (im.format or "jpeg").lower()
        except Exception as e:
            raise MediaError(f"unreadable image: {e}")
        return {"jpeg": "jpg"}.get(fmt, fmt), data
    max_px, quality = IMG_PRESETS[level]
    return "webp", image_low(data, max_px, quality)


def image_to_jpeg(data, max_px=1600, quality=85):
    """LXMF image (usually WebP) -> JPEG for WhatsApp."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGB")
            im.thumbnail((max_px, max_px))
            buf = io.BytesIO()
            im.save(buf, format="jpeg", quality=quality)
            return buf.getvalue()
    except Exception as e:
        raise MediaError(f"unreadable image: {e}")


# ------------------------------------------------------------------ audio

def audio_to_codec2(src_path, mode_name="2400"):
    """Audio file (WhatsApp Opus/ogg voice note or other) -> raw Codec2 frames."""
    if mode_name not in CODEC2_BY_NAME:
        raise MediaError(f"invalid Codec2 mode: {mode_name}")
    data = _ffmpeg([
        "-i", src_path, "-vn", "-ac", "1", "-ar", "8000",
        "-af", "highpass=f=200,lowpass=f=3400,dynaudnorm",
        "-c:a", "libcodec2", "-mode", mode_name, "-f", "codec2raw", "pipe:1",
    ])
    return CODEC2_BY_NAME[mode_name], data


OPUS_LEVELS = {"medium": (12, 16000), "high": (24, 24000)}   # kbit/s, Hz


def _opus_ogg(src_path, kbps, rate):
    return _ffmpeg(["-i", src_path, "-vn", "-ac", "1", "-ar", str(rate), "-c:a", "libopus",
                    "-b:a", f"{kbps}k", "-application", "voip", "-f", "ogg", "pipe:1"])


def audio_for(src_path, level, codec2_mode="2400"):
    """WhatsApp audio -> (LXMF audio mode, bytes) at the requested level.
    low = Codec2; medium/high = re-encoded Opus ogg; original = Opus ogg unchanged."""
    if level == "low":
        return audio_to_codec2(src_path, codec2_mode)
    if level == "original":
        with open(src_path, "rb") as f:
            raw = f.read()
        if raw[:4] == b"OggS":
            return AM_OPUS_OGG, raw
        level = "high"   # not an ogg: re-encode it, Sideband only reads Opus/Codec2
    kbps, rate = OPUS_LEVELS[level]
    return AM_OPUS_OGG, _opus_ogg(src_path, kbps, rate)


def lxmf_audio_to_ogg(audio_mode, data):
    """FIELD_AUDIO content -> mono 48 kHz Opus ogg, suitable as a WhatsApp voice note."""
    out_args = ["-ar", "48000", "-ac", "1", "-c:a", "libopus", "-b:a", "24k",
                "-application", "voip", "-f", "ogg", "pipe:1"]
    if audio_mode in CODEC2_MODES:
        name, _ = CODEC2_MODES[audio_mode]
        return _ffmpeg(["-f", "codec2raw", "-mode", name, "-i", "pipe:0"] + out_args, stdin=data)
    if audio_mode == AM_OPUS_OGG:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(data)
            tmp = f.name
        try:
            return _ffmpeg(["-i", tmp] + out_args)
        finally:
            os.unlink(tmp)
    raise MediaError(f"unsupported LXMF audio mode: {audio_mode:#x}")


def codec2_seconds(audio_mode, nbytes):
    _, bps = CODEC2_MODES[audio_mode]
    return nbytes * 8 / bps
