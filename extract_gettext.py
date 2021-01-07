#!/usr/bin/env python3

"""
Extract strings::

    python3 extract_gettext.py

Run tests::

    python3 -m doctest -v extract_gettext.py

"""

import re
import subprocess
from collections import deque


def js_files():
    res = subprocess.run(
        ["git", "ls-files", "*js", "*mjs"],
        capture_output=True,
        encoding="utf-8",
    )
    return res.stdout.splitlines()


def extract_args(part):
    parens = 0
    quote = ""
    for idx, c in enumerate(part):
        if c == quote:
            quote = ""
        elif quote:
            pass
        elif c in {"'", '"'}:
            quote = c
        elif c == "(":
            parens += 1
        elif c == ")":
            parens -= 1

        if parens == 0:
            return part[1:idx]

    return ""


def gettext_calls(source):
    """Extract *gettext calls from code

    >>> list(gettext_calls("gettext('abc')"))
    ["gettext('abc')"]
    >>> list(gettext_calls("abc def gettext('abc') xyz gettext blub"))
    ["gettext('abc')"]
    >>> list(gettext_calls("abc ngettext('singular', 'plural', someVar) def"))
    ["ngettext('singular', 'plural', someVar)"]
    >>> list(gettext_calls("abc def gettext ( ' abc ' ) xyz"))
    ["gettext(' abc ')"]
    >>> list(gettext_calls("gettext(':-/')"))
    ["gettext(':-/')"]
    >>> list(gettext_calls("gettext(':-)')"))
    ["gettext(':-)')"]
    >>> list(gettext_calls("abc gettext('xyz' def pgettext('ctx', 'str') xzz"))
    ["pgettext('ctx', 'str')"]
    """

    parts = deque(part.strip() for part in re.split(r"\b(\w*gettext)\b", source))

    while parts:
        top = parts.popleft()
        if not top.endswith("gettext"):
            continue

        if parts and (args := extract_args(parts.popleft())):
            yield f"{top}({args.strip()})"


if __name__ == "__main__":
    calls = set()
    for file in js_files():
        with open(file, encoding="utf-8") as f:
            calls |= set(gettext_calls(f.read()))
    print("\n".join(sorted(calls, key=lambda c: c.lower())))
