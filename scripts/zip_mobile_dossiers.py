# -*- coding: utf-8 -*-
"""Zip the mobile-dossiers/ folder for iPhone with FORWARD-SLASH entry names.

Windows PowerShell 5.1 (Compress-Archive AND .NET ZipFile.CreateFromDirectory) writes
backslash path separators into the archive, which iOS Files extracts as flat files named
'audio\\dossiers\\x.mp3' with no real folders -> every relative asset 404s. Python's zipfile
always uses forward slashes, so the extracted tree is correct on iOS/macOS/Android.
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "mobile-dossiers")
OUT = os.path.join(ROOT, "mobile-dossiers.zip")


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _dirs, files in os.walk(SRC):
            for fn in files:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, SRC).replace(os.sep, "/")  # force '/'
                z.write(full, rel)
                count += 1
    # verify
    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
        bad = [n for n in names if "\\" in n]
        has_html = "uap-command-center.html" in names
        audio = [n for n in names if n.startswith("audio/")]
        vendor = [n for n in names if n.startswith("vendor/")]
    size_mb = round(os.path.getsize(OUT) / (1024 * 1024), 2)
    print(f"wrote {count} files -> {OUT} ({size_mb} MB)")
    print(f"backslash entries (must be 0): {len(bad)}")
    print(f"html at root: {has_html}")
    print(f"audio/ entries: {len(audio)} | vendor/ entries: {len(vendor)}")
    print("sample:", audio[0] if audio else "(none)")


if __name__ == "__main__":
    main()
