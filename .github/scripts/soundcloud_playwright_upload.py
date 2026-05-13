#!/usr/bin/env python3
"""
Upload SoundCloud depuis une vraie session navigateur (Playwright + profil persistant).

DataDome regarde IP + empreinte TLS + enchaînement + cookies + « est-ce un navigateur ».
L’API multipart brute (requests/curl_cffi) peut passer /me mais échouer sur POST /tracks :
ici on rejoue le parcours réel (DOM, input file, même stack TLS/JA3 que Chromium).


Première utilisation (sur le Mac du runner, une fois) :
  python3 .github/scripts/soundcloud_playwright_upload.py \\
    --profile ~/.432hz/soundcloud-playwright-profile \\
    --login-only

Ensuite, le workflow self-hosted utilise le même dossier --profile.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path


def _default_profile() -> Path:
    return Path.home() / ".432hz" / "soundcloud-playwright-profile"


def login_only(profile: Path, channel: str | None) -> int:
    from playwright.sync_api import sync_playwright

    profile.mkdir(parents=True, exist_ok=True)
    print("Ouverture du navigateur — connecte-toi à SoundCloud (page signin ou tracks).")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            channel=channel,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://soundcloud.com/signin", wait_until="domcontentloaded")
        try:
            input("Quand la session est OK (tu vois ton compte), appuie sur Entrée pour enregistrer le profil…\n")
        except EOFError:
            print("(stdin fermé — fermeture du navigateur pour sauvegarder le profil.)", file=sys.stderr)
        finally:
            ctx.close()
    print(f"Profil enregistré : {profile}")
    return 0


def upload_track(mp3: Path, title: str | None, profile: Path, channel: str | None, headed: bool) -> int:
    from playwright.sync_api import sync_playwright

    if not mp3.is_file():
        print(f"❌ Fichier introuvable : {mp3}", file=sys.stderr)
        return 2
    if not profile.is_dir():
        print(
            f"❌ Profil Playwright absent : {profile}\n"
            f"   Lance une fois : python3 {Path(__file__).name} --profile {profile} --login-only",
            file=sys.stderr,
        )
        return 3

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            headless=not headed,
            channel=channel,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(120_000)
            page.goto("https://soundcloud.com/upload", wait_until="domcontentloaded")
            time.sleep(2)

            u = page.url
            if "/sign-in" in u or "/login" in u or ("signin" in u and "soundcloud.com" in u):
                print(
                    "❌ Session expirée ou non connecté — refais --login-only avec le même --profile.",
                    file=sys.stderr,
                )
                return 4

            inputs = page.locator('input[type="file"]')
            if inputs.count() == 0:
                print("❌ Aucun input[type=file] sur /upload — la page a peut‑être changé.", file=sys.stderr)
                return 5
            inputs.first.set_input_files(str(mp3.resolve()))
            print(f"📤 Fichier envoyé au navigateur : {mp3.name}")
            time.sleep(3)
            if title:
                try:
                    ph = page.get_by_placeholder(re.compile(r"title|titre|name", re.I))
                    if ph.count() > 0:
                        ph.first.fill(title)
                except Exception:
                    pass

            # Attendre un indicateur de traitement / formulaire (SPA)
            for _ in range(180):
                time.sleep(1)
                url = page.url
                html = page.content()
                if "captcha" in html.lower() or "captcha-delivery" in html:
                    print("❌ Captcha / DataDome visible dans la page — résous-le manuellement une fois avec --headed.", file=sys.stderr)
                    return 6
                if "/you/tracks" in url or "/tracks/" in url or (mp3.stem[:12].lower() in html.lower() and "upload" not in url):
                    print(f"✅ Upload semble terminé — {url[:80]}")
                    break
                if "error" in html.lower() and "upload" in html.lower():
                    print("❌ Erreur affichée sur la page upload.", file=sys.stderr)
                    return 7
            else:
                print("⚠️ Délai dépassé — vérifie manuellement sur soundcloud.com/you/tracks", file=sys.stderr)

            return 0
        finally:
            ctx.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Upload SoundCloud via Playwright (session navigateur)")
    ap.add_argument("--profile", type=Path, default=None, help="Dossier profil persistant Playwright")
    ap.add_argument("--mp3", type=Path, default=None, help="Fichier MP3 à uploader")
    ap.add_argument("--title", type=str, default=None, help="Titre (optionnel)")
    ap.add_argument("--login-only", action="store_true", help="Ouvre le navigateur pour te connecter (première fois)")
    ap.add_argument("--headed", action="store_true", help="Upload avec fenêtre visible (debug / captcha)")
    ap.add_argument(
        "--channel",
        type=str,
        default=None,
        help="ex: chrome (utilise Chrome installé). Défaut : Chromium Playwright",
    )
    args = ap.parse_args()
    profile = args.profile or _default_profile()

    if args.login_only:
        return login_only(profile, args.channel)

    if not args.mp3:
        ap.error("--mp3 requis sauf avec --login-only")

    return upload_track(args.mp3, args.title, profile, args.channel, args.headed)


if __name__ == "__main__":
    raise SystemExit(main())
