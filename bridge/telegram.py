"""Minimal Telegram Bot API client (standard library only).

Long polling with getUpdates, multipart uploads, file downloads, and 429 back-off.
The base URL is configurable so that tests can point it at a fake server.
Also usable from the shell (setup.sh):  python3 telegram.py getme TOKEN
                                        python3 telegram.py discover TOKEN SECONDS
"""

import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

DEFAULT_API = "https://api.telegram.org"


class TelegramError(Exception):
    def __init__(self, description, code=0, retry_after=0):
        super().__init__(description)
        self.code = code
        self.retry_after = retry_after


class BotAPI:
    def __init__(self, token, api_base=None, timeout=70):
        self.token = token
        self.base = (api_base or os.environ.get("HEIMDALL_TG_API") or DEFAULT_API).rstrip("/")
        self.timeout = timeout

    # ---------------------------------------------------------------- low level
    def call(self, method, params=None, files=None, timeout=None):
        url = f"{self.base}/bot{self.token}/{method}"
        if files:
            body, ctype = _multipart(params or {}, files)
        else:
            body, ctype = json.dumps(params or {}).encode(), "application/json"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read())
            except Exception:
                raise TelegramError(f"HTTP {e.code}", e.code) from None
        except (urllib.error.URLError, OSError) as e:
            raise TelegramError(f"network: {getattr(e, 'reason', e)}") from None
        if not data.get("ok"):
            p = data.get("parameters") or {}
            raise TelegramError(data.get("description", "error"), data.get("error_code", 0), p.get("retry_after", 0))
        return data["result"]

    def call_retry(self, method, params=None, files=None, tries=4):
        """Like call(), but waits and retries on 429 (flood limit) and on network errors."""
        for i in range(tries):
            try:
                return self.call(method, params, files)
            except TelegramError as e:
                if i == tries - 1 or not (e.code == 429 or e.code == 0 or e.code >= 500):
                    raise
                time.sleep(min(e.retry_after or 2 ** i, 60))

    # ---------------------------------------------------------------- methods
    def get_me(self):
        return self.call("getMe", timeout=20)

    def get_updates(self, offset=None, poll=50):
        p = {"timeout": poll, "allowed_updates": ["message", "channel_post"]}
        if offset is not None:
            p["offset"] = offset
        return self.call("getUpdates", p, timeout=poll + 20)

    def download(self, file_id, dest):
        f = self.call_retry("getFile", {"file_id": file_id})
        url = f"{self.base}/file/bot{self.token}/{f['file_path']}"
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as out:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
        except (urllib.error.URLError, OSError) as e:
            raise TelegramError(f"download: {getattr(e, 'reason', e)}") from None
        return dest

    def send_text(self, chat_id, text):
        return self.call_retry("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                               "disable_web_page_preview": True})

    def send_file(self, chat_id, kind, path, caption="", filename=None, mime=None):
        """kind: photo | voice | video | document"""
        method = {"photo": "sendPhoto", "voice": "sendVoice", "video": "sendVideo", "document": "sendDocument"}[kind]
        params = {"chat_id": chat_id}
        if caption:
            params.update(caption=caption[:1024], parse_mode="HTML")
        with open(path, "rb") as f:
            data = f.read()
        name = filename or os.path.basename(path)
        return self.call_retry(method, params, {kind: (name, data, mime or _guess(name))})


def _guess(name):
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def _multipart(fields, files):
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        if not isinstance(v, str):
            v = json.dumps(v)
        out += [f"--{b}\r\n".encode(), f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode(),
                v.encode(), b"\r\n"]
    for k, (name, data, mime) in files.items():
        safe = name.replace('"', "_").replace("\r", "_").replace("\n", "_")
        out += [f"--{b}\r\n".encode(),
                f'Content-Disposition: form-data; name="{k}"; filename="{safe}"\r\n'.encode(),
                f"Content-Type: {mime}\r\n\r\n".encode(), data, b"\r\n"]
    out.append(f"--{b}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={b}"


# -------------------------------------------------------------------- shell helpers for setup.sh
def _cli():
    cmd, token = sys.argv[1], sys.argv[2]
    api = BotAPI(token)
    try:
        if cmd == "getme":
            me = api.get_me()
            # username, whether privacy mode is off (needed to see every group message)
            print(me.get("username", ""), "yes" if me.get("can_read_all_group_messages") else "no")
        elif cmd == "discover":
            # list the chats the bot has seen in the next N seconds: "id<TAB>type<TAB>title"
            seen, offset, end = {}, None, time.time() + float(sys.argv[3])
            while time.time() < end:
                for u in api.get_updates(offset, poll=max(1, min(10, int(end - time.time())))):
                    offset = u["update_id"] + 1
                    m = u.get("message") or u.get("channel_post") or {}
                    c = m.get("chat") or {}
                    if c.get("type") in ("group", "supergroup", "channel") and c["id"] not in seen:
                        seen[c["id"]] = f"{c['id']}\t{c['type']}\t{c.get('title', '')}"
                        print(seen[c["id"]], flush=True)
            if offset is not None:
                api.get_updates(offset, poll=0)   # mark them as read so the bridge does not replay them
        else:
            sys.exit(2)
    except TelegramError as e:
        print(f"ERROR {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _cli()
