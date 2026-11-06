#!/usr/bin/env python3
"""Small config.ini editor used by setup.sh. Keeps comments and layout (configparser would not).

  cfgtool.py get     FILE SECTION KEY
  cfgtool.py set     FILE SECTION KEY VALUE
"""
import re
import sys

OLD_SECTION, OLD_KEY = {}, {}
NEW_SECTION, NEW_KEY = {}, {}

SEC = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KV = re.compile(r"^(\s*)([A-Za-z0-9_]+)(\s*[=:]\s*)(.*?)\s*$")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def write(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def find(lines, section, key):
    """(section_header_index, key_line_index or None)."""
    names = {section, NEW_SECTION.get(section, section)}
    keys = {key, NEW_KEY.get(key, key)}
    sec_i, cur = None, None
    for i, line in enumerate(lines):
        m = SEC.match(line)
        if m:
            cur = m.group(1).strip()
            if cur in names and sec_i is None:
                sec_i = i
            continue
        if cur in names:
            kv = KV.match(line)
            if kv and not line.lstrip().startswith(("#", ";")) and kv.group(2) in keys:
                return sec_i, i
    return sec_i, None


def cmd_get(path, section, key):
    lines = read(path)
    _, i = find(lines, section, key)
    if i is not None:
        print(KV.match(lines[i]).group(4))


def cmd_set(path, section, key, value):
    lines = read(path)
    sec_i, i = find(lines, section, key)
    if i is not None:
        m = KV.match(lines[i])
        lines[i] = f"{m.group(1)}{m.group(2)} = {value}"
    elif sec_i is not None:
        lines.insert(sec_i + 1, f"{key} = {value}")
    else:
        lines += ["", f"[{section}]", f"{key} = {value}"]
    write(path, lines)


if __name__ == "__main__":
    c, a = sys.argv[1], sys.argv[2:]
    {"get": cmd_get, "set": cmd_set}[c](*a)
