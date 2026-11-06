"""Fake Telegram Bot API server for tests.

Usage: fake_tg.py PORT WORKDIR
  - updates to deliver: drop JSON files in WORKDIR/inbox/ (each a list of "message" objects or one object);
    files referenced by file_id are served from WORKDIR/files/<file_id>
  - every send* call is appended to WORKDIR/sent.jsonl (uploaded files saved in WORKDIR/uploads/)
"""

import json
import os
import sys
import threading
import time
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, WORK = int(sys.argv[1]), sys.argv[2]
for d in ("inbox", "files", "uploads"):
    os.makedirs(os.path.join(WORK, d), exist_ok=True)
lock = threading.Lock()
queue, next_id = [], [1]
PRIVACY_OFF = os.environ.get("FAKE_TG_PRIVACY_OFF", "1") == "1"


def pull_inbox():
    for n in sorted(os.listdir(os.path.join(WORK, "inbox"))):
        p = os.path.join(WORK, "inbox", n)
        try:
            items = json.load(open(p))
        except Exception:
            continue
        os.unlink(p)
        for m in items if isinstance(items, list) else [items]:
            key = "channel_post" if m.get("chat", {}).get("type") == "channel" else "message"
            m.setdefault("date", int(time.time()))
            with lock:
                queue.append({"update_id": next_id[0], key: m})
                next_id[0] += 1


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):   # file downloads: /file/bot<token>/<path>
        parts = self.path.split("/")
        if len(parts) >= 4 and parts[1] == "file":
            p = os.path.join(WORK, "files", parts[-1])
            if os.path.isfile(p):
                data = open(p, "rb").read()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        token, method = self.path.split("/")[1][3:], self.path.split("/")[2]
        if token == "bad":
            return self.reply({"ok": False, "error_code": 401, "description": "Unauthorized"}, 401)
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        ctype = self.headers.get("Content-Type", "")
        params, files = {}, {}
        if ctype.startswith("multipart/"):
            msg = BytesParser(policy=default).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + raw)
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if part.get_filename():
                    data = part.get_payload(decode=True)
                    dest = os.path.join(WORK, "uploads", f"{time.time():.6f}-{part.get_filename()}")
                    open(dest, "wb").write(data)
                    files[name] = {"filename": part.get_filename(), "size": len(data), "path": dest,
                                   "mime": part.get_content_type()}
                else:
                    params[name] = part.get_payload(decode=True).decode()
        elif raw:
            params = json.loads(raw)

        if method == "getMe":
            return self.reply({"ok": True, "result": {"id": 42, "is_bot": True, "username": "test_bot",
                                                       "can_read_all_group_messages": PRIVACY_OFF}})
        if method == "getUpdates":
            off = params.get("offset")
            with lock:
                if off is not None:
                    queue[:] = [u for u in queue if u["update_id"] >= int(off)]
            end = time.time() + min(float(params.get("timeout", 0)), 2)
            while True:
                pull_inbox()
                with lock:
                    out = list(queue)
                if out or time.time() >= end:
                    return self.reply({"ok": True, "result": out})
                time.sleep(0.2)
        if method == "getFile":
            fid = params["file_id"]
            if not os.path.isfile(os.path.join(WORK, "files", fid)):
                return self.reply({"ok": False, "error_code": 400, "description": "Bad Request: invalid file_id"}, 400)
            return self.reply({"ok": True, "result": {"file_id": fid, "file_path": f"documents/{fid}"}})
        if method.startswith("send"):
            with open(os.path.join(WORK, "sent.jsonl"), "a") as f:
                f.write(json.dumps({"method": method, "params": params, "files": files}) + "\n")
            return self.reply({"ok": True, "result": {"message_id": int(time.time() * 1000) % 100000}})
        return self.reply({"ok": False, "error_code": 404, "description": "Not Found"}, 404)


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
