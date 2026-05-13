#!/usr/bin/env python3
"""
Fusionne published_videos.json + media_urls_manual.json → media_urls_catalog.json
pour articles, posts et docs (URLs centralisées).

Usage :
  cd youtube_uploader && python3 export_media_urls_catalog.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main() -> None:
    pub_path = BASE / "published_videos.json"
    manual_path = BASE / "media_urls_manual.json"
    out_path = BASE / "media_urls_catalog.json"

    if not pub_path.exists():
        raise SystemExit(f"Manquant : {pub_path}")

    pub = json.loads(pub_path.read_text(encoding="utf-8"))
    manual: dict = {}
    if manual_path.exists():
        manual = json.loads(manual_path.read_text(encoding="utf-8"))

    uploads = []
    for key, v in sorted(
        pub.get("videos", {}).items(),
        key=lambda x: (x[1].get("published_date") or ""),
    ):
        uploads.append(
            {
                "tracker_key": key,
                "title": v.get("title"),
                "url": v.get("url"),
                "video_id": v.get("video_id"),
                "published_date": v.get("published_date"),
            }
        )

    catalog = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "soundcloud_profile": manual.get("soundcloud_profile"),
        "manual_notes": manual.get("notes"),
        "manual_tracks": manual.get("tracks", {}),
        "youtube_uploads_432hz": uploads,
    }

    out_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"OK → {out_path} ({len(uploads)} vidéo(s) YouTube 432 Hz)")


if __name__ == "__main__":
    main()
