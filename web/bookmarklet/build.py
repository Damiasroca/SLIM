"""Build the pastable `javascript:...` bookmarklet URL from slim-quota.js.

Usage:
    python build.py
Writes:
    bookmarklet.txt  (the `javascript:...` string, ready to paste)

Kept intentionally tiny — no external minifier. Just strips block/line
comments, trims blank lines, collapses whitespace, and URL-encodes.
"""
import re
import urllib.parse
from pathlib import Path

HERE = Path(__file__).parent
src = (HERE / "slim-quota.js").read_text(encoding="utf-8")

# Strip /* ... */ comments (non-greedy, DOTALL).
src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)

lines = []
for line in src.splitlines():
    stripped = line.strip()
    if not stripped:
        continue
    stripped = re.sub(r"\s+//[^\"']*$", "", stripped)
    if stripped.startswith("//"):
        continue
    lines.append(stripped)

compact = " ".join(lines)
compact = re.sub(r"\s+", " ", compact).strip()

encoded = urllib.parse.quote(compact, safe="")
url = "javascript:" + encoded

out = HERE / "bookmarklet.txt"
out.write_text(url + "\n", encoding="utf-8")
print(f"Wrote {out} ({len(url)} chars)")
