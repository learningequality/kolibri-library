#!/usr/bin/env python
"""
Spot-check that zipfix.py has been applied across chefdata/zipfiles/.

Samples a random subset of {hash}/webroot.zip files, extracts them in memory,
and counts:
  - files containing `Utils.mobileDeviceFlag=true`   (should be 0 — offending code)
  - files containing `Utils.mobileDeviceFlag=false`  (the fixed marker)
  - files starting with `b'` which indicates the old buggy write corrupted them

Throwaway script, not committed. Run from the worktree root.
"""
import os
import random
import sys
import zipfile
from collections import Counter

ROOT = "chefdata/zipfiles"
SAMPLE_SIZE = int(os.environ.get("SAMPLE", 15))
OFFENDING = b"Utils.mobileDeviceFlag=true"
FIXED = b"Utils.mobileDeviceFlag=false"


def scan_zip(zip_path):
    """Return (offending_hits, fixed_hits, corrupted_files) across .js/.html inside zip."""
    off = fix = corrupt = 0
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.filelist:
                if not info.filename.endswith((".js", ".html")):
                    continue
                with zf.open(info) as f:
                    head = f.read(4)
                    rest = f.read()
                content = head + rest
                if head.startswith(b"b'"):
                    corrupt += 1
                if OFFENDING in content:
                    off += 1
                if FIXED in content:
                    fix += 1
    except zipfile.BadZipFile:
        return None
    return off, fix, corrupt


def main():
    all_hashes = [
        d for d in os.listdir(ROOT)
        if os.path.isdir(os.path.join(ROOT, d)) and len(d) == 32
    ]
    print(f"Found {len(all_hashes)} hash dirs under {ROOT}")

    sample = random.sample(all_hashes, min(SAMPLE_SIZE, len(all_hashes)))
    totals = Counter()
    missing_webroot = 0
    bad_zips = []

    for h in sample:
        zp = os.path.join(ROOT, h, "webroot.zip")
        if not os.path.exists(zp):
            missing_webroot += 1
            continue
        result = scan_zip(zp)
        if result is None:
            bad_zips.append(zp)
            continue
        off, fix, corrupt = result
        totals["offending"] += off
        totals["fixed"] += fix
        totals["corrupted"] += corrupt
        flag = " <<<" if (off or corrupt) else ""
        print(f"  {h}: offending={off}, fixed={fix}, corrupt={corrupt}{flag}")

    print()
    print(f"Sample size: {len(sample)}")
    print(f"Missing webroot.zip: {missing_webroot}")
    print(f"BadZipFile errors:   {len(bad_zips)}")
    print(f"Totals across sample: {dict(totals)}")
    if totals["offending"] or totals["corrupted"]:
        print("FAIL — zipfix output looks incomplete.")
        sys.exit(1)
    print("OK — no offending code and no bytestring corruption in sample.")


if __name__ == "__main__":
    main()
