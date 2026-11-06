#!/usr/bin/env python3
"""Telegram group/channel <-> Reticulum/LXMF bridge.

Attaches to rnsd as a client of the shared instance (never opens serial ports)
and to Telegram through a bot (Bot API, long polling).
Usage: heimdall.py [config.ini]
"""

import configparser
import os
import queue
import re
import sys
import threading
import time

import LXMF
import RNS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Core, Limits  # noqa: E402
from i18n import LANGS, make_t, norm_level  # noqa: E402
from telegram import BotAPI, TelegramError  # noqa: E402

VERSION = "alpha0.1"
HEX32 = re.compile(r"^[0-9a-f]{32}$")


def _hashes(s):
    return [h.strip().replace("<", "").replace(">", "").lower() for h in (s or "").split(",") if h.strip()]


def load_config(path):
    cp = configparser.ConfigParser()
    cp.optionxform = str   # keep the case of alias names
    if path and not cp.read(path):
        sys.exit("Config not found / Config non trovata: " + path)
    g = lambda sec, key, d=None: cp.get(sec, key, fallback=d) if cp.has_section(sec) else d
    lang = (g("bridge", "language", "en") or "en").strip().lower()[:2]
    lang = lang if lang in LANGS else "en"
    base = os.path.expanduser(g("bridge", "dir", "~/.heimdall"))
    lim = Limits()
    for k, typ in (("confirm_threshold_kb", int), ("max_file_mb", float), ("codec2_mode", str),
                   ("link_kbps", float), ("pending_ttl_h", float), ("quality_img", str),
                   ("quality_audio", str), ("rate_per_min", int)):
        v = g("limits", k)
        if v is not None and v.strip():
            setattr(lim, k, typ(v.strip()))
    lim.quality_img = norm_level(lim.quality_img, "low")
    lim.quality_audio = norm_level(lim.quality_audio, "low")
    yes = lambda v: str(v).strip().lower() in ("yes", "true", "1", "on", "si", "sì")
    return {
        "lang": lang,
        "dir": base,
        "name": g("bridge", "name") or "Heimdall",
        "announce_min": float(g("bridge", "announce_min", "15")),
        "max_receive_mb": float(g("bridge", "max_receive_mb", "10")),
        "rns_config": os.path.expanduser(g("bridge", "rns_config")) if g("bridge", "rns_config") else None,
        "propagation": (g("bridge", "propagation_node", "") or "").strip().strip("<>").lower(),
        "token": (g("telegram", "token", "") or "").strip(),
        "chat_id": (g("telegram", "chat_id", "") or "").strip(),
        "api_base": (g("telegram", "api_base", "") or "").strip() or None,
        "targets": _hashes(g("lxmf", "targets")),
        "senders": (g("lxmf", "senders", "anyone") or "anyone").strip().lower(),
        "subscriptions": yes(g("lxmf", "subscriptions", "no")),
        "echo": yes(g("lxmf", "echo", "no")),
        "blocked": _hashes(g("lxmf", "blocked")),
        "aliases": {k.strip("<>").lower(): v for k, v in cp.items("names")} if cp.has_section("names") else {},
        "limits": lim,
    }


class LxmfSide:
    MAX_TRIES = 4

    def __init__(self, cfg, t):
        self.cfg, self.t = cfg, t
        self.reticulum = RNS.Reticulum(cfg["rns_config"])
        if not self.reticulum.is_connected_to_shared_instance:
            RNS.log(t("not_shared"), RNS.LOG_WARNING)
        id_path = os.path.join(cfg["dir"], "identity")
        if os.path.isfile(id_path):
            self.identity = RNS.Identity.from_file(id_path)
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(id_path)
        # delivery_limit is in KB: how big an LXMF message we accept (photos/files to post on Telegram)
        self.router = LXMF.LXMRouter(identity=self.identity, storagepath=os.path.join(cfg["dir"], "lxmf"),
                                     delivery_limit=int(cfg["max_receive_mb"] * 1000))
        self.dest = self.router.register_delivery_identity(self.identity, display_name=cfg["name"])
        self.router.register_delivery_callback(self._on_delivery)
        if cfg["propagation"]:
            self.router.set_outbound_propagation_node(bytes.fromhex(cfg["propagation"]))
        self.core = None
        self.outq, self.qlock = [], threading.Lock()
        RNS.log(t("address_log", addr=RNS.prettyhexrep(self.dest.hash)), RNS.LOG_NOTICE)
        try:
            with open(os.path.join(cfg["dir"], "address.txt"), "w") as f:
                f.write(self.dest.hash.hex() + "\n")
        except OSError:
            pass

    def announce(self):
        self.router.announce(self.dest.hash)

    @staticmethod
    def name_of(src_hex):
        try:
            app_data = RNS.Identity.recall_app_data(bytes.fromhex(src_hex))
            return LXMF.display_name_from_app_data(app_data) if app_data else None
        except Exception:
            return None

    def _on_delivery(self, lxm):
        src = lxm.source_hash.hex()
        try:
            self.core.on_lxmf(src, lxm.content_as_string(), lxm.fields)
        except Exception as e:
            RNS.trace_exception(e)
            self.send(src, self.t("internal_error", err=e), {})

    def send(self, dest_hex, text, fields):
        with self.qlock:
            self.outq.append({"to": bytes.fromhex(dest_hex), "text": text, "fields": fields or {},
                              "t0": time.time(), "asked": 0, "tries": 0})
        RNS.log(self.t("queued_log", dest=dest_hex[:8], chars=len(text or ""),
                       fields=sorted((fields or {}).keys())), RNS.LOG_VERBOSE)

    def pump(self):
        with self.qlock:
            pending, self.outq = self.outq, []
        keep = []
        for m in pending:
            short = m["to"].hex()[:8]
            ident = RNS.Identity.recall(m["to"])
            if ident is None:
                if time.time() - m["asked"] > 15:
                    RNS.Transport.request_path(m["to"])
                    m["asked"] = time.time()
                if time.time() - m["t0"] < 3600:
                    keep.append(m)
                else:
                    RNS.log(self.t("dropped_log", dest=short), RNS.LOG_WARNING)
                continue
            dest = RNS.Destination(ident, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
            lxm = LXMF.LXMessage(dest, self.dest, m["text"], fields=m["fields"] or None,
                                 desired_method=LXMF.LXMessage.DIRECT)
            lxm.register_delivery_callback(lambda l, m=m, s=short: RNS.log(
                self.t("delivered_log", dest=s, n=m["tries"] + 1), RNS.LOG_NOTICE))
            lxm.register_failed_callback(lambda l, m=m: self._on_failed(l, m))
            self.router.handle_outbound(lxm)
        with self.qlock:
            self.outq = keep + self.outq

    def _on_failed(self, lxm, m):
        short = m["to"].hex()[:8]
        m["tries"] += 1
        if m["tries"] < self.MAX_TRIES:
            RNS.log(self.t("retry_log", dest=short, n=m["tries"], max=self.MAX_TRIES), RNS.LOG_WARNING)
            m["asked"], m["t0"] = 0, time.time()
            threading.Timer(30, lambda: self._requeue(m)).start()
        elif self.cfg["propagation"]:
            RNS.log(self.t("propagation_log", dest=short), RNS.LOG_WARNING)
            retry = LXMF.LXMessage(lxm.get_destination(), self.dest, lxm.content, title=lxm.title,
                                   fields=lxm.fields, desired_method=LXMF.LXMessage.PROPAGATED)
            self.router.handle_outbound(retry)
        else:
            RNS.log(self.t("lost_log", dest=short), RNS.LOG_ERROR)

    def _requeue(self, m):
        with self.qlock:
            self.outq.append(m)


class TelegramSide:
    def __init__(self, cfg, t):
        self.api = BotAPI(cfg["token"], cfg["api_base"])
        self.t = t
        self.core = None
        self.sendq = queue.Queue()
        self.offset_path = os.path.join(cfg["dir"], "tg_offset")

    def _load_offset(self):
        try:
            with open(self.offset_path) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def _save_offset(self, off):
        with open(self.offset_path, "w") as f:
            f.write(str(off))

    def poll_loop(self):
        offset, logged_in, last_err = self._load_offset(), False, ""
        while True:
            try:
                if not logged_in:
                    me = self.api.get_me()
                    RNS.log(self.t("tg_connected", user=me.get("username", "?")), RNS.LOG_NOTICE)
                    if not me.get("can_read_all_group_messages") and self.core.chat_kind == "group":
                        RNS.log(self.t("tg_privacy"), RNS.LOG_WARNING)
                    logged_in = True
                updates = self.api.get_updates(offset)
                self.core.tg_status, last_err = "ok", ""
                for u in updates:
                    offset = u["update_id"] + 1
                    try:
                        self.core.on_tg_update(u)
                    except Exception as e:
                        RNS.trace_exception(e)
                    self._save_offset(offset)
            except TelegramError as e:
                self.core.tg_status = "down"
                msg = self.t("tg_conflict") if e.code == 409 else self.t("tg_error", err=e)
                if msg != last_err:
                    RNS.log(msg, RNS.LOG_ERROR)
                    last_err = msg
                time.sleep(e.retry_after or (30 if e.code in (401, 404, 409) else 5))

    def send(self, cmd):
        self.sendq.put(cmd)

    def send_loop(self):
        while True:
            cmd = self.sendq.get()
            chat = self.core.chat_id
            try:
                if cmd["kind"] == "text":
                    self.api.send_text(chat, cmd["text"])
                else:
                    self.api.send_file(chat, cmd["kind"], cmd["path"], cmd.get("caption", ""),
                                       cmd.get("filename"), cmd.get("mime"))
            except TelegramError as e:
                RNS.log(self.t("tg_error", err=e), RNS.LOG_ERROR)
                self.core.tg_failed(cmd, e)
            except Exception as e:
                RNS.trace_exception(e)
                self.core.tg_failed(cmd, e)
            finally:
                if cmd.get("path"):
                    try:
                        os.unlink(cmd["path"])
                    except OSError:
                        pass


def main():
    cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    t = make_t(cfg["lang"])
    if not cfg["token"] or not re.fullmatch(r"-?\d+", cfg["chat_id"]):
        sys.exit(t("token_missing"))
    for h in cfg["targets"] + cfg["blocked"]:
        if not HEX32.match(h):
            sys.exit(t("target_invalid", value=h))
    spool = os.path.join(cfg["dir"], "spool")
    os.makedirs(spool, mode=0o700, exist_ok=True)

    RNS.log(t("starting", version=VERSION), RNS.LOG_NOTICE)
    lx = LxmfSide(cfg, t)
    tg = TelegramSide(cfg, t)
    chat_kind = "group"
    try:
        chat_kind = "channel" if tg.api.call("getChat", {"chat_id": int(cfg["chat_id"])}, timeout=20).get("type") == "channel" else "group"
    except TelegramError:
        pass
    core = Core(os.path.join(cfg["dir"], "state.json"), spool, cfg["limits"], cfg["chat_id"], cfg["targets"],
                lx_send=lx.send, tg_send=tg.send, tg_fetch=tg.api.download, name_of=lx.name_of,
                senders=cfg["senders"], subscriptions=cfg["subscriptions"], echo=cfg["echo"],
                blocked=cfg["blocked"], aliases=cfg["aliases"], chat_kind=chat_kind,
                log=lambda s: RNS.log(s, RNS.LOG_NOTICE), version="Heimdall " + VERSION, lang=cfg["lang"])
    lx.core = tg.core = core
    threading.Thread(target=tg.poll_loop, daemon=True).start()
    threading.Thread(target=tg.send_loop, daemon=True).start()

    lx.announce()
    last_ann = last_clean = time.time()
    while True:
        lx.pump()
        now = time.time()
        if now - last_ann > cfg["announce_min"] * 60:
            lx.announce()
            last_ann = now
        if now - last_clean > 600:
            core.expire_pending()
            core.cleanup_spool()
            last_clean = now
        time.sleep(1)


if __name__ == "__main__":
    main()
