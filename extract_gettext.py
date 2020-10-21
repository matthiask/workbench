#!/usr/bin/env python3

import re
import subprocess


def js_files():
    res = subprocess.run(
        ["git", "ls-files", "*js", "*mjs"],
        capture_output=True,
        encoding="utf-8",
    )
    return res.stdout.splitlines()


def gettext_calls(file):
    with open(file, encoding="utf-8") as f:
        return [
            match[0]
            for match in
            re.findall(
                r"""\b(\w*gettext\(\s*(['"]).+?\2\s*\))""",
                f.read(),
            )
        ]


if __name__ == "__main__":
    calls = []
    for file in js_files():
        calls.extend(gettext_calls(file))
    print("\n".join(sorted(set(calls))))
