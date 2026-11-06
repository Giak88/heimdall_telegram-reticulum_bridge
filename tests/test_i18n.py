"""Message catalogue checks: every key has EN and IT, placeholders match, help mentions the commands."""
import os
import string
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
from core import COMMANDS  # noqa: E402
from i18n import LANGS, LEVELS, MSG, make_t, norm_level  # noqa: E402

fields = lambda s: {f for _, f, _, _ in string.Formatter().parse(s) if f}
bad = []
for key, entry in MSG.items():
    for lang in LANGS:
        if not entry.get(lang):
            bad.append(f"{key}: missing {lang}")
    if fields(entry["en"]) != fields(entry["it"]):
        bad.append(f"{key}: placeholders differ")
assert not bad, "\n".join(bad)
for lvl in LEVELS:
    assert "level_" + lvl in MSG
for lang, words in {"en": ("/download", "/status", "/join", "/leave", "/help"),
                    "it": ("/scarica", "/stato", "/entra", "/esci", "/aiuto")}.items():
    h = make_t(lang)("help", where="x")
    for w in words:
        assert w in h, (lang, w)
        assert w in COMMANDS, w
assert norm_level("Medio") == "medium" and norm_level("nope") is None
print(f"i18n ok: {len(MSG)} messages x {len(LANGS)} languages")
