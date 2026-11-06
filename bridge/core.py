"""Bridge logic, independent of RNS and of the network (testable on its own).

The core receives:
  - Telegram updates                    -> on_tg_update(update)
  - LXMF messages from anyone           -> on_lxmf(source_hex, text, fields)
and calls:
  - lx_send(dest_hex, text, fields)     LXMF message to one address
  - tg_send(cmd)                        post to the Telegram chat (done by a worker; failures come
                                        back through tg_failed(cmd, error))
  - tg_fetch(file_id, dest_path)        download a Telegram file
  - name_of(source_hex)                 display name announced by an LXMF address, or None
"""

import html
import json
import mimetypes
import os
import re
import threading
import time
from dataclasses import dataclass

from i18n import LEVELS, make_t, norm_level
from media import (CODEC2_MODES, MediaError, audio_for, codec2_seconds, image_for,
                   image_to_jpeg, lxmf_audio_to_ogg)

FIELD_FILE_ATTACHMENTS = 0x05
FIELD_IMAGE = 0x06
FIELD_AUDIO = 0x07

TG_UPLOAD_MAX = 50 * 1024 * 1024      # Bot API upload limit
TG_DOWNLOAD_MAX = 20 * 1024 * 1024    # Bot API download limit


@dataclass
class Limits:
    confirm_threshold_kb: int = 32    # above: notice + /download N
    max_file_mb: float = 0.9          # above: not deliverable over LXMF (stock router limit 1000 KB)
    quality_img: str = "low"          # low | medium | high | original
    quality_audio: str = "low"
    codec2_mode: str = "2400"
    link_kbps: float = 1.2            # only for the time estimate
    pending_ttl_h: float = 24
    rate_per_min: int = 10            # max messages per LXMF sender per minute (0 = no limit)
    history_h: float = 48             # how long sent messages stay available for /repeat
    history_max: int = 100            # ...and how many (0 = no history)


def human_size(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def human_eta(nbytes, kbps):
    s = nbytes * 8 / (kbps * 1000)
    if s < 90:
        return f"~{s:.0f} s"
    if s < 5400:
        return f"~{s / 60:.0f} min"
    return f"~{s / 3600:.1f} h"


ICON = {"photo": "🖼", "voice": "🎤", "audio": "🎵", "video": "🎬", "video_note": "🎬", "animation": "🎞",
        "document": "📎"}

COMMANDS = {
    "/help": "help", "/aiuto": "help", "/?": "help",
    "/status": "status", "/stato": "status",
    "/download": "download", "/scarica": "download",
    "/join": "join", "/entra": "join", "/iscriviti": "join",
    "/leave": "leave", "/esci": "leave",
    "/repeat": "repeat", "/ripeti": "repeat",
}


class Core:
    def __init__(self, state_path, spool_dir, limits, chat_id, targets, lx_send, tg_send, tg_fetch,
                 name_of=lambda h: None, senders="anyone", subscriptions=False, echo=False, blocked=(),
                 aliases=None, chat_kind="group", log=print, version="", lang="en"):
        self.state_path = state_path
        self.spool = spool_dir
        self.lim = limits
        self.targets = [h.lower() for h in targets]
        self._raw_send, self.tg_send, self.tg_fetch, self.name_of = lx_send, tg_send, tg_fetch, name_of
        self.lx_send = self._send   # every message to a recipient is remembered for /repeat
        self.senders = senders                  # anyone | targets
        self.subscriptions = subscriptions      # may LXMF users /join?
        self.echo = echo                        # repeat LXMF posts to the other LXMF recipients
        self.blocked = {h.lower() for h in blocked}
        self.aliases = {k.lower(): v for k, v in (aliases or {}).items()}
        self.chat_kind = chat_kind
        self.log, self.version, self.t = log, version, make_t(lang)
        self.tg_status = "unknown"
        self.lock = threading.RLock()
        self.rate = {}
        self.st = {"chat_id": None, "subscribers": [], "pending": {}, "next_pending": 1,
                   "history": {}, "next_hist": 1}
        if os.path.exists(state_path):
            try:
                with open(state_path) as f:
                    self.st.update(json.load(f))
            except Exception as e:
                self.log(self.t("state_unreadable", err=e))
        self.config_chat_id = int(chat_id)
        if self.st.get("chat_id_from") != self.config_chat_id:
            # config changed (or first run): forget a migration recorded for another chat
            self.st["chat_id"], self.st["chat_id_from"] = None, self.config_chat_id

    @property
    def chat_id(self):
        return self.st.get("chat_id") or self.config_chat_id

    def recipients(self):
        return list(dict.fromkeys(self.targets + self.st["subscribers"]))

    def _save(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.st, f)
        os.replace(tmp, self.state_path)

    def _quality(self, kind):
        return norm_level(self.lim.quality_img if kind == "img" else self.lim.quality_audio, "low")

    # =============================================================== Telegram -> LXMF
    def on_tg_update(self, upd):
        m = upd.get("message") or upd.get("channel_post")
        if not m:
            return
        chat = m.get("chat") or {}
        with self.lock:
            if chat.get("id") != self.chat_id:
                self.log(self.t("ignore_chat", id=chat.get("id"), title=chat.get("title", chat.get("username", ""))))
                return
            if m.get("migrate_to_chat_id"):
                self.st["chat_id"] = m["migrate_to_chat_id"]
                self.log(self.t("chat_migrated", new=m["migrate_to_chat_id"]))
                self._save()
                return
            try:
                self._tg_message(m)
            finally:
                self._save()

    @staticmethod
    def _sender(m):
        if m.get("author_signature"):
            return m["author_signature"]
        u = m.get("from") or {}
        if u:
            name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x)
            return name or ("@" + u["username"] if u.get("username") else "?")
        s = m.get("sender_chat") or m.get("chat") or {}
        return s.get("title") or "?"

    def _broadcast(self, text, fields=None):
        for dest in self.recipients():
            self.lx_send(dest, text, fields or {})

    # ----------------------------------------------------------- history / repeat
    def _send(self, dest, text, fields):
        if dest in self.recipients():
            self._remember(dest, text, fields)
        self._raw_send(dest, text, fields)

    def _remember(self, dest, text, fields):
        if self.lim.history_max <= 0:
            return
        hid = self.st["next_hist"]
        self.st["next_hist"] += 1
        entry = {"ts": time.time(), "text": text, "blob": None}
        if fields:
            blob = os.path.join(self.spool, f"hist-{hid}")
            try:
                with open(blob, "w") as f:
                    json.dump(_encode_field(fields), f)
                entry["blob"] = blob
            except OSError:
                pass
        hist = self.st["history"].setdefault(dest, [])
        hist.append(entry)
        while len(hist) > self.lim.history_max:
            _unlink(hist.pop(0).get("blob"))

    def _expire_history(self):
        cutoff = time.time() - self.lim.history_h * 3600
        for dest, hist in list(self.st["history"].items()):
            for e in [e for e in hist if e["ts"] < cutoff]:
                _unlink(e.get("blob"))
                hist.remove(e)
            if not hist:
                del self.st["history"][dest]

    def _cmd_repeat(self, src, arg):
        """/repeat N: send again the last N messages the bridge sent to this address, oldest first."""
        t = self.t
        if not arg.isdigit() or int(arg) == 0:
            return self._raw_send(src, t("repeat_usage"), {})
        sel = self.st["history"].get(src, [])[-int(arg):]
        if not sel:
            return self._raw_send(src, t("repeat_none"), {})
        self._raw_send(src, t("repeat_start", n=len(sel)), {})
        for e in sel:
            fields = {}
            if e.get("blob"):
                try:
                    with open(e["blob"]) as f:
                        fields = _decode_field(json.load(f))
                except (OSError, ValueError):
                    pass
            fmt = "%d/%m %H:%M" if time.time() - e["ts"] > 20 * 3600 else "%H:%M"
            self._raw_send(src, f"\u21bb {time.strftime(fmt, time.localtime(e['ts']))} {e['text']}", fields)

    def _tg_message(self, m):
        head = self._sender(m)
        caption = m.get("caption", "")
        if "text" in m:
            self._broadcast(f"{head}: {m['text']}")
            return
        for kind in ("photo", "voice", "audio", "video", "video_note", "animation", "document"):
            if kind in m:
                return self._tg_media(kind, m, head, caption)
        t = self.t
        if "sticker" in m:
            self._broadcast(f"{head}: [{t('sticker')} {m['sticker'].get('emoji', '')}]".replace(" ]", "]"))
        elif "location" in m:
            loc = m["location"]
            self._broadcast(f"{head}: 📍 {t('location')} {loc['latitude']:.5f}, {loc['longitude']:.5f} "
                            f"https://www.openstreetmap.org/?mlat={loc['latitude']:.5f}&mlon={loc['longitude']:.5f}")
        elif "contact" in m:
            c = m["contact"]
            self._broadcast(f"{head}: 👤 {t('contact')} {c.get('first_name', '')} {c.get('phone_number', '')}".strip())
        elif "poll" in m:
            p = m["poll"]
            opts = " / ".join(o["text"] for o in p.get("options", []))
            self._broadcast(f"{head}: 📊 {t('poll')}: {p.get('question', '')} ({opts})")
        elif any(k in m for k in ("new_chat_members", "left_chat_member", "pinned_message", "new_chat_title",
                                  "group_chat_created", "supergroup_chat_created")):
            return   # service messages: not forwarded
        else:
            kind = next((k for k in m if k not in ("message_id", "from", "chat", "date", "sender_chat",
                                                  "message_thread_id", "reply_to_message", "entities")), "?")
            self._broadcast(f"{head}: " + t("unsupported", kind=kind))

    def _tg_media(self, kind, m, head, caption):
        t = self.t
        obj = m[kind][-1] if kind == "photo" else m[kind]     # photo: the biggest size comes last
        size = obj.get("file_size", 0)
        icon = ICON.get(kind, "📎")
        name = obj.get("file_name") or f"{kind}{_ext(obj.get('mime_type'), kind)}"
        label = f"{t('kind_' + kind)} {name}" if kind in ("document", "video", "animation", "audio") else t("kind_" + kind)
        cap = self.lim.max_file_mb * 1024 * 1024

        convertible = kind in ("photo", "voice") or (kind == "audio" and size <= TG_DOWNLOAD_MAX)
        if convertible:
            if size > TG_DOWNLOAD_MAX:
                return self._broadcast(t("media_too_big", head=head, icon=icon, label=label,
                                         size=human_size(size), caption=caption).strip())
            path = os.path.join(self.spool, f"tg-{obj['file_unique_id'] if 'file_unique_id' in obj else time.time()}")
            try:
                self.tg_fetch(obj["file_id"], path)
                with open(path, "rb") as f:
                    raw = f.read()
                field, label, note = self._convert(kind, path, raw, obj)
            except Exception as e:
                return self._broadcast(t("media_unavailable", head=head, icon=icon, label=label, err=e,
                                         caption=caption).strip())
            finally:
                _unlink(path)
            nbytes = _field_size(field)
            if nbytes > cap:
                return self._broadcast(t("media_too_big", head=head, icon=icon, label=label + note,
                                         size=human_size(nbytes), caption=caption).strip())
            if nbytes <= self.lim.confirm_threshold_kb * 1024:
                return self._broadcast(f"{head}: {caption}".strip().rstrip(":") if caption else head, field)
            pid = self._hold({"head": head, "caption": caption, "label": label + note, "size": nbytes,
                              "blob": self._spool_field(field)})
        else:
            # video, document...: sent unchanged, downloaded only when (and if) someone asks
            if size > cap or size > TG_DOWNLOAD_MAX:
                return self._broadcast(t("media_too_big", head=head, icon=icon, label=label,
                                         size=human_size(size), caption=caption).strip())
            if size and size <= self.lim.confirm_threshold_kb * 1024:
                try:
                    field = self._fetch_attachment(obj["file_id"], name)
                except Exception as e:
                    return self._broadcast(t("media_unavailable", head=head, icon=icon, label=label, err=e,
                                             caption=caption).strip())
                return self._broadcast(f"{head}: {caption}".strip().rstrip(":") if caption else head, field)
            pid = self._hold({"head": head, "caption": caption, "label": label, "size": size,
                              "file_id": obj["file_id"], "name": name})
        self._broadcast(t("media_pending", head=head, icon=icon, label=self.st["pending"][pid]["label"],
                          size=human_size(self.st["pending"][pid]["size"]),
                          eta=human_eta(self.st["pending"][pid]["size"], self.lim.link_kbps),
                          pid=pid, caption=caption).strip())

    def _convert(self, kind, path, raw, obj):
        """-> (LXMF field, label, note). Steps down a level until it fits under max_file_mb."""
        cap = self.lim.max_file_mb * 1024 * 1024
        is_audio = kind in ("voice", "audio")
        want = self._quality("audio" if is_audio else "img")
        for lvl in LEVELS[:LEVELS.index(want) + 1][::-1]:
            lname = self.t("level_" + lvl)
            if is_audio:
                mode, payload = audio_for(path, lvl, self.lim.codec2_mode)
                secs = obj.get("duration") or (codec2_seconds(mode, len(payload)) if mode in CODEC2_MODES else 0)
                field, label = {FIELD_AUDIO: [mode, payload]}, self.t("label_voice", secs=f"{secs:.0f}", level=lname)
            else:
                typ, payload = image_for(raw, lvl)
                field, label = {FIELD_IMAGE: [typ, payload]}, self.t("label_image", level=lname)
            if len(payload) <= cap or lvl == "low":
                note = self.t("reduced_note", level=lname) if lvl != want else ""
                return field, label, note

    def _fetch_attachment(self, file_id, name):
        path = os.path.join(self.spool, f"tg-{time.time():.6f}")
        try:
            self.tg_fetch(file_id, path)
            with open(path, "rb") as f:
                return {FIELD_FILE_ATTACHMENTS: [[name, f.read()]]}
        finally:
            _unlink(path)

    def _spool_field(self, field):
        p = os.path.join(self.spool, f"pending-{time.time():.6f}.json")
        with open(p, "w") as f:
            json.dump(_encode_field(field), f)
        return p

    def _hold(self, item):
        pid = str(self.st["next_pending"])
        self.st["next_pending"] += 1
        item["t"] = time.time()
        self.st["pending"][pid] = item
        return pid

    def expire_pending(self):
        with self.lock:
            now = time.time()
            for pid, p in list(self.st["pending"].items()):
                if now - p["t"] > self.lim.pending_ttl_h * 3600:
                    if p.get("blob"):
                        _unlink(p["blob"])
                    del self.st["pending"][pid]
            self._expire_history()
            self._save()

    # =============================================================== LXMF -> Telegram
    def on_lxmf(self, src, text, fields):
        src = src.lower()
        text = (text or "").strip()
        with self.lock:
            try:
                self._lxmf(src, text, fields or {})
            finally:
                self._save()

    def name(self, src):
        return self.aliases.get(src) or self.name_of(src) or f"<{src[:8]}>"

    def _allowed(self, src):
        if src in self.blocked:
            return "why_blocked"
        if self.senders == "targets" and src not in self.recipients():
            return "why_not_target"
        return None

    def _rate_ok(self, src):
        if not self.lim.rate_per_min:
            return True
        now = time.time()
        q = [x for x in self.rate.get(src, []) if now - x < 60]
        if len(q) >= self.lim.rate_per_min:
            self.rate[src] = q
            return False
        q.append(now)
        self.rate[src] = q
        return True

    def _lxmf(self, src, text, fields):
        t = self.t
        reply = lambda s: self.lx_send(src, s, {})
        if text.startswith("/") and not fields:
            return self._command(src, text)
        why = self._allowed(src)
        if why:
            self.log(t("ignore_sender", src=src, why=t(why)))
            if why == "why_not_target":
                reply(t("not_allowed"))
            return
        if not self._rate_ok(src):
            return reply(t("rate_limited", n=self.lim.rate_per_min))

        who = html.escape(self.name(src))
        body = html.escape(text)
        caption = f"<b>{who}</b>" + (f": {body}" if body else "")
        posted = False
        if FIELD_IMAGE in fields:
            try:
                jpg = image_to_jpeg(fields[FIELD_IMAGE][1])
                self.tg_send({"kind": "photo", "path": self._tmp(".jpg", jpg), "caption": caption,
                              "origin": src, "what": t("what_image")})
                posted = True
            except MediaError as e:
                reply(t("tg_send_failed", what=t("what_image"), err=e))
        if FIELD_AUDIO in fields:
            try:
                ogg = lxmf_audio_to_ogg(fields[FIELD_AUDIO][0], fields[FIELD_AUDIO][1])
                self.tg_send({"kind": "voice", "path": self._tmp(".ogg", ogg),
                              "caption": caption if not posted else f"<b>{who}</b>", "origin": src,
                              "what": t("what_voice")})
                posted = True
            except MediaError as e:
                reply(t("tg_send_failed", what=t("what_voice"), err=e))
        for att in fields.get(FIELD_FILE_ATTACHMENTS) or []:
            name = str(att[0] or "file")
            data = att[1]
            if len(data) > TG_UPLOAD_MAX:
                reply(t("tg_too_big", name=name, size=human_size(len(data))))
                continue
            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
            kind = "video" if mime.startswith("video/") else "document"
            self.tg_send({"kind": kind, "path": self._tmp("-" + _safe(name), data), "filename": name, "mime": mime,
                          "caption": caption if not posted else f"<b>{who}</b>", "origin": src,
                          "what": t("what_file", name=name)})
            posted = True
        if not posted:
            if not text:
                return reply(t("empty"))
            for part in _split(caption, 4000):
                self.tg_send({"kind": "text", "text": part, "origin": src, "what": t("what_text")})
        self.log(t("posted_log", src=src[:8], what=", ".join(
            [k for k, f in (("text", text), ("image", FIELD_IMAGE in fields), ("audio", FIELD_AUDIO in fields),
                            ("files", FIELD_FILE_ATTACHMENTS in fields)) if f])))
        if self.echo:
            for dest in self.recipients():
                if dest != src:
                    self.lx_send(dest, f"{self.name(src)}: {text}" if text else self.name(src), fields)

    def tg_failed(self, cmd, err):
        if cmd.get("origin"):
            self.lx_send(cmd["origin"], self.t("tg_send_failed", what=cmd.get("what", "?"), err=err), {})

    def _tmp(self, suffix, data):
        p = os.path.join(self.spool, f"out-{time.time():.6f}{suffix}")
        with open(p, "wb") as f:
            f.write(data)
        return p

    # =============================================================== commands
    def _command(self, src, text):
        t = self.t
        parts = text.split(maxsplit=1)
        raw, arg = parts[0].lower(), (parts[1].strip() if len(parts) > 1 else "")
        cmd = COMMANDS.get(raw)
        reply = lambda s: self.lx_send(src, s, {})
        where = t("where_channel" if self.chat_kind == "channel" else "where_group")
        if cmd == "help":
            reply(t("help", where=where))
        elif cmd == "status":
            reply(t("status", version=self.version, tg=t("tg_" + self.tg_status) if self.tg_status in ("ok", "down", "unknown")
                    else self.tg_status, chat=self.chat_id, targets=len(self.targets),
                    subs=len(self.st["subscribers"]), pending=len(self.st["pending"])))
        elif cmd == "download":
            if not arg.isdigit():
                return reply(t("download_usage"))
            p = self.st["pending"].get(arg)
            if not p:
                return reply(t("download_none", n=arg))
            if src not in self.recipients():
                return reply(t("not_allowed"))
            try:
                if p.get("blob"):
                    with open(p["blob"]) as f:
                        field = _decode_field(json.load(f))
                else:
                    field = self._fetch_attachment(p["file_id"], p["name"])
            except Exception as e:
                return reply(t("download_failed", err=e))
            # stays available for the other recipients until it expires
            self.lx_send(src, f"{p['head']}: {p['caption']}" if p["caption"] else p["head"], field)
        elif cmd == "repeat":
            if src not in self.recipients():
                return reply(t("not_allowed"))
            self._cmd_repeat(src, arg)
        elif cmd == "join":
            if src in self.targets or src in self.st["subscribers"]:
                return reply(t("join_already"))
            if not self.subscriptions or src in self.blocked:
                return reply(t("join_closed"))
            self.st["subscribers"].append(src)
            reply(t("join_ok", where=where))
        elif cmd == "leave":
            if src in self.targets:
                return reply(t("join_fixed"))
            if src not in self.st["subscribers"]:
                return reply(t("leave_none"))
            self.st["subscribers"].remove(src)
            reply(t("leave_ok"))
        else:
            reply(t("unknown_command", cmd=raw))

    def cleanup_spool(self, max_age=3600):
        """Delete outgoing temp files left behind (the worker deletes them after sending)."""
        now = time.time()
        for n in os.listdir(self.spool):
            p = os.path.join(self.spool, n)
            if n.startswith(("out-", "tg-")) and now - os.path.getmtime(p) > max_age:
                _unlink(p)


# -------------------------------------------------------------------- helpers
def _field_size(field):
    v = next(iter(field.values()))
    return len(v[1])


def _split(s, n):
    return [s[i:i + n] for i in range(0, len(s), n)] or [""]


def _safe(name):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[-60:]


def _unlink(p):
    if not p:
        return
    try:
        os.unlink(p)
    except OSError:
        pass


_EXT = {"video/mp4": ".mp4", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "image/jpeg": ".jpg",
        "image/gif": ".gif", "application/pdf": ".pdf"}


def _ext(mime, kind):
    return _EXT.get(mime or "", {"photo": ".jpg", "voice": ".ogg", "video": ".mp4", "video_note": ".mp4",
                                 "animation": ".mp4"}.get(kind, ""))


def _encode_field(field):
    def enc(x):
        if isinstance(x, (bytes, bytearray)):
            return {"__b": bytes(x).hex()}
        if isinstance(x, list):
            return [enc(i) for i in x]
        return x
    return {str(k): enc(v) for k, v in field.items()}


def _decode_field(d):
    def dec(x):
        if isinstance(x, dict) and "__b" in x:
            return bytes.fromhex(x["__b"])
        if isinstance(x, list):
            return [dec(i) for i in x]
        return x
    return {int(k): dec(v) for k, v in d.items()}
