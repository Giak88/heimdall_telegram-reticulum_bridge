"""Config loading. Needs rns + lxmf importable."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
from heimdall import load_config  # noqa: E402


def cfg(text):
    with tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False) as f:
        f.write(text)
    try:
        return load_config(f.name)
    finally:
        os.unlink(f.name)


A = "0123456789abcdef0123456789abcdef"
c = cfg(f"""[bridge]
language = it
[telegram]
token = 123:ABC
chat_id = -100123
[lxmf]
targets = <{A.upper()}>, {'b' * 32}
senders = targets
subscriptions = yes
blocked = {'e' * 32}
[limits]
quality_img = medio
rate_per_min = 3
[names]
{'d' * 32} = Mario IZ0ABC
""")
assert c["lang"] == "it" and c["token"] == "123:ABC" and c["chat_id"] == "-100123"
assert c["targets"] == [A, "b" * 32] and c["senders"] == "targets" and c["subscriptions"] is True
assert c["blocked"] == ["e" * 32] and c["echo"] is False
assert c["limits"].quality_img == "medium" and c["limits"].rate_per_min == 3
assert c["aliases"] == {"d" * 32: "Mario IZ0ABC"}
d = cfg("[telegram]\ntoken = x\nchat_id = 1\n")
assert d["lang"] == "en" and d["targets"] == [] and d["senders"] == "anyone" and d["name"] == "Heimdall"
assert d["dir"].endswith("/.heimdall") and d["max_receive_mb"] == 10 and d["limits"].quality_audio == "low"
print("config ok")
