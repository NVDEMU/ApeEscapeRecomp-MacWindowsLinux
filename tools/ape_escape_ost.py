#!/usr/bin/env python3
"""Load and download individual tracks from the user's selected Internet Archive OST."""
from __future__ import annotations
import argparse, json, re, ssl, sys, urllib.parse, urllib.request
from pathlib import Path

ITEM = "ape-escape-1999-ost"
METADATA_URL = f"https://archive.org/metadata/{ITEM}"
USER_AGENT = "ApeEscapeRecomp-OSTPlayer/1.0"

def _context():
    ca = Path(__file__).resolve().parent / "cacert.pem"
    return ssl.create_default_context(cafile=str(ca)) if ca.is_file() else ssl.create_default_context()

def _request(url, context, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout, context=context)

def _tracks(context):
    with _request(METADATA_URL, context) as response:
        metadata = json.loads(response.read().decode("utf-8"))
    rows = []
    for item in metadata.get("files", []):
        name = item.get("name", "")
        if not isinstance(name, str) or not name.lower().startswith("ape escape - ") or not name.lower().endswith(".mp3"):
            continue
        if Path(name).name != name or "/" in name or "\\" in name or any(ch in name for ch in "\t\r\n"):
            continue
        title = re.sub(r"^Ape Escape\s*-\s*", "", name, flags=re.I)
        title = re.sub(r"\.mp3$", "", title, flags=re.I)
        title = re.sub(r"^\s*\d+\.\s*", "", title)
        number = re.match(r"^Ape Escape\s*-\s*(\d+)\.", name, flags=re.I)
        rows.append({"filename": name, "title": title or name, "number": int(number.group(1)) if number else 99999,
                     "size": int(item.get("size", 0) or 0)})
    rows.sort(key=lambda r: (r["number"], r["title"].casefold()))
    if not rows:
        raise RuntimeError("No matching MP3 files were found in this Archive.org item.")
    return rows

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    listing = sub.add_parser("list"); listing.add_argument("manifest", type=Path)
    download = sub.add_parser("download"); download.add_argument("filename"); download.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    try:
        context = _context()
        rows = _tracks(context)
        if args.action == "list":
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.manifest.with_suffix(args.manifest.suffix + ".part")
            with temporary.open("w", encoding="utf-8", newline="\n") as out:
                for row in rows:
                    out.write(f'{row["filename"]}\t{row["title"]}\t{row["size"]}\n')
            temporary.replace(args.manifest)
            print(f"Loaded {len(rows)} tracks from Internet Archive.")
            return 0
        if args.filename not in {row["filename"] for row in rows} or Path(args.filename).name != args.filename or "\\" in args.filename:
            raise RuntimeError("Requested filename is not a track in the selected Archive.org item.")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        target = args.output_dir / args.filename
        if target.is_file() and target.stat().st_size:
            return 0
        temporary = target.with_suffix(target.suffix + ".part")
        url = f"https://archive.org/download/{ITEM}/{urllib.parse.quote(args.filename, safe='')}"
        try:
            with _request(url, context, timeout=180) as response, temporary.open("wb") as out:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk: break
                    out.write(chunk)
                out.flush()
            if not temporary.is_file() or not temporary.stat().st_size:
                raise RuntimeError("Archive.org returned an empty file.")
            temporary.replace(target)
        except Exception:
            try: temporary.unlink()
            except OSError: pass
            raise
        print(f"Downloaded selected track: {target}")
        return 0
    except Exception as exc:
        print(f"OST player: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
