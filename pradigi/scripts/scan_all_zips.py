#!/usr/bin/env python
"""
Pre-flight scan of every chefdata/zipfiles/{hash}/webroot.zip.

Reports anything that would fail ricecooker's HTML5 validation:
  - missing webroot.zip entirely
  - zip that isn't a valid zip file
  - zip with no entries (empty EOCD)
  - zip missing index.html
  - index.html with a <body> that has no text and no children

Used before a smoke run to enumerate all problem zips at once, rather
than fixing one per crash.
"""
import os
import sys
import zipfile

import html5lib

ROOT = "chefdata/zipfiles"


def scan_zip(zp):
    try:
        with zipfile.ZipFile(zp) as zf:
            names = zf.namelist()
            if not names:
                return "empty_zip"
            if "index.html" not in names:
                return "no_index_html"
            try:
                idx = zf.read("index.html")
            except Exception as e:
                return f"unreadable_index: {e}"
            try:
                dom = html5lib.parse(idx, namespaceHTMLElements=False)
            except Exception as e:
                return f"parse_error: {e}"
            body = dom.find("body")
            if body is None:
                return "no_body"
            body_children = [
                c for c in body.iter()
                if isinstance(c.tag, str) and c.tag != "body"
            ]
            body_text = (body.text or "").strip()
            if not body_text and not body_children:
                return "empty_body"
    except zipfile.BadZipFile as e:
        return f"bad_zip: {e}"
    except Exception as e:
        return f"error: {e}"
    return None


def main():
    hashes = sorted(
        d for d in os.listdir(ROOT)
        if os.path.isdir(os.path.join(ROOT, d)) and len(d) == 32
    )
    print(f"scanning {len(hashes)} hash dirs under {ROOT}")
    problems = []
    for h in hashes:
        zp = os.path.join(ROOT, h, "webroot.zip")
        if not os.path.exists(zp):
            problems.append((h, "missing_webroot"))
            continue
        reason = scan_zip(zp)
        if reason:
            problems.append((h, reason))
    print(f"\n{len(problems)} problem zips:")
    for h, reason in problems:
        print(f"  {h}  {reason}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
