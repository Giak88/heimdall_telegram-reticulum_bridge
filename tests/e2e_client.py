"""LXMF client used by e2e.sh: announces itself, writes to the bridge, prints what it receives.
Usage: e2e_client.py <rns_config> <workdir> <bridge_hash_hex>"""
import io
import os
import sys
import time

import LXMF
import RNS
from PIL import Image

cfg, work, bridge_hex = sys.argv[1], sys.argv[2], sys.argv[3]
RNS.Reticulum(cfg, loglevel=RNS.LOG_WARNING)
ident = RNS.Identity.from_file(os.path.join(work, "client.id"))
router = LXMF.LXMRouter(identity=ident, storagepath=os.path.join(work, "client-lxmf"))
dest = router.register_delivery_identity(ident, display_name="Test client")
router.register_delivery_callback(lambda m: print("RECEIVED:", repr(m.content_as_string()), sorted(m.fields or {}), flush=True))
router.announce(dest.hash)
bh = bytes.fromhex(bridge_hex)
t0 = time.time()
while RNS.Identity.recall(bh) is None and time.time() - t0 < 20:
    RNS.Transport.request_path(bh)
    time.sleep(1)
bdest = RNS.Destination(RNS.Identity.recall(bh), RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")


def send(text, fields=None):
    m = LXMF.LXMessage(bdest, dest, text, fields=fields, desired_method=LXMF.LXMessage.DIRECT)
    m.register_delivery_callback(lambda x: print("DELIVERED to bridge:", text[:20], flush=True))
    router.handle_outbound(m)


time.sleep(3)
router.announce(dest.hash)          # so that the bridge learns our display name
time.sleep(3)
send("hello from the LoRa")
time.sleep(3)
b = io.BytesIO()
Image.new("RGB", (320, 240), (10, 120, 200)).save(b, "webp", quality=22)
send("a photo", {LXMF.FIELD_IMAGE: ["webp", b.getvalue()]})
time.sleep(3)
send("/status")
time.sleep(float(os.environ.get("WAIT", "12")))
print("END", flush=True)
