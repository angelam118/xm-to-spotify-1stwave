#!/usr/bin/env python3
"""
xm_to_spotify.py
Accumulates tracks from XMPlaylists (station=1stwave) into Spotify playlists
named "SiriusXM 1st Wave Archive — Vol. N", auto-creating new volumes when the
current volume approaches Spotify's 10,000-track limit.
"""

import os
import time
import json
import base64
import logging
from typing import List, Optional, Tuple
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------------- CONFIG ----------------
XM_CHANNEL = "1stwave"
XM_API_URL = f"https://xmplaylist.com/api/station/{XM_CHANNEL}"

PLAYLIST_PREFIX = "SiriusXM 1st Wave Archive"
# safety threshold before reaching 10_000 (will create a new volume at threshold)
PLAYLIST_MAX = 10000
PLAYLIST_THRESHOLD = 9900

# Local metadata/caches
META_FILE = "meta.json"   # holds { "current_volume": int, "current_playlist_id": str }
SEEN_FILE = "seen.json"   # holds list of "artist - title" strings already handled

# Spotify env vars (must be provided)
# SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN, SPOTIFY_USER_ID
SP_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SP_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SP_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
SP_USER_ID = os.getenv("SPOTIFY_USER_ID")

if not all([SP_CLIENT_ID, SP_CLIENT_SECRET, SP_REFRESH_TOKEN, SP_USER_ID]):
    logging.error("Missing one or more required Spotify environment variables: "
                  "SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN, SPOTIFY_USER_ID")
    raise SystemExit(1)

# ---------------- Helpers ----------------

def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default

def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_access_token() -> str:
    """Use the stored refresh token to fetch a fresh access token."""
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": SP_REFRESH_TOKEN,
    }
    auth = (SP_CLIENT_ID, SP_CLIENT_SECRET)
    r = requests.post(token_url, data=payload, auth=auth, timeout=30)
    r.raise_for_status()
    token_data = r.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError("Could not obtain access token from Spotify.")
    return access_token

def spotify_headers(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# ---------------- XM -> Parse ----------------
def fetch_xm_tracks() -> List[Tuple[str, str, str]]:
    """Return list of (title, artist, canonical_key) newest-first from xmplaylist."""
    try:
        r = requests.get(XM_API_URL, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logging.error("Failed to fetch XMPlaylists data: %s", e)
        return []

    results = []
    for item in data.get("tracks", []):
        title = (item.get("song") or "").strip()
        artist = (item.get("artist") or "").strip()
        if title and artist:
            key = f"{artist.lower()} - {title.lower()}"
            results.append((title, artist, key))
    # The API returns most recent first; we want to add older tracks first to preserve chronology
    results.reverse()
    return results

# ---------------- Spotify operations ----------------
def create_playlist(access_token: str, volume: int) -> str:
    """Create playlist and return its spotify id."""
    url = f"https://api.spotify.com/v1/users/{SP_USER_ID}/playlists"
    name = f"{PLAYLIST_PREFIX} — Vol. {volume}"
    payload = {
        "name": name,
        "description": f"Archive of SiriusXM 1st Wave, volume {volume} (auto-generated).",
        "public": False
    }
    r = requests.post(url, headers=spotify_headers(access_token), json=payload, timeout=30)
    r.raise_for_status()
    pid = r.json()["id"]
    logging.info("Created playlist %s (id=%s)", name, pid)
    return pid

def get_playlist_total_tracks(access_token: str, playlist_id: str) -> int:
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}?fields=tracks.total"
    r = requests.get(url, headers=spotify_headers(access_token), timeout=20)
    r.raise_for_status()
    return r.json()["tracks"]["total"]

def spotify_search_track(access_token: str, title: str, artist: str) -> Optional[str]:
    """Return the first matching track URI or None."""
    q = f'track:{title} artist:{artist}'
    url = "https://api.spotify.com/v1/search"
    params = {"q": q, "type": "track", "limit": 1}
    r = requests.get(url, headers=spotify_headers(access_token), params=params, timeout=20)
    if r.status_code != 200:
        logging.debug("Spotify search failed: %s %s", r.status_code, r.text)
        return None
    items = r.json().get("tracks", {}).get("items", [])
    if not items:
        # fallback: broader search
        q2 = f"{title} {artist}"
        params2 = {"q": q2, "type": "track", "limit": 1}
        r2 = requests.get(url, headers=spotify_headers(access_token), params=params2, timeout=20)
        if r2.status_code == 200:
            its = r2.json().get("tracks", {}).get("items", [])
            if its:
                return its[0]["uri"]
        return None
    return items[0]["uri"]

def add_tracks_to_playlist(access_token: str, playlist_id: str, uris: List[str]) -> bool:
    if not uris:
        return True
    # Spotify accepts up to 100 URIs per request
    for i in range(0, len(uris), 100):
        chunk = uris[i:i+100]
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        payload = {"uris": chunk}
        r = requests.post(url, headers=spotify_headers(access_token), json=payload, timeout=30)
        if r.status_code not in (200, 201):
            logging.error("Failed to add tracks: %s %s", r.status_code, r.text)
            return False
        time.sleep(0.2)  # gentle pacing
    return True

# ---------------- Main updater ----------------
def main():
    meta = load_json(META_FILE, default={})
    seen = set(load_json(SEEN_FILE, default=[]))

    current_volume = meta.get("current_volume", 1)
    current_playlist_id = meta.get("current_playlist_id")

    access_token = get_access_token()

    # If we don't yet have a playlist id in meta, find/create the latest volume
    if not current_playlist_id:
        # create Vol.1
        current_playlist_id = create_playlist(access_token, current_volume)
        meta["current_volume"] = current_volume
        meta["current_playlist_id"] = current_playlist_id
        save_json(META_FILE, meta)

    # Ensure the playlist exists and hasn't reached threshold; if it has, create next
    try:
        total = get_playlist_total_tracks(access_token, current_playlist_id)
    except Exception as e:
        logging.warning("Could not get playlist info (maybe deleted). Creating new playlist: %s", e)
        current_volume += 1
        current_playlist_id = create_playlist(access_token, current_volume)
        meta["current_volume"] = current_volume
        meta["current_playlist_id"] = current_playlist_id
        save_json(META_FILE, meta)
        total = 0

    if total >= PLAYLIST_THRESHOLD:
        logging.info("Current playlist at %s tracks which is >= threshold %s. Creating new volume.", total, PLAYLIST_THRESHOLD)
        current_volume += 1
        current_playlist_id = create_playlist(access_token, current_volume)
        meta["current_volume"] = current_volume
        meta["current_playlist_id"] = current_playlist_id
        save_json(META_FILE, meta)
        total = 0

    # Fetch xm tracks (oldest first so we preserve order)
    xm_tracks = fetch_xm_tracks()
    logging.info("Fetched %d xm tracks to consider.", len(xm_tracks))

    to_add_uris = []
    new_count = 0
    for title, artist, key in xm_tracks:
        if key in seen:
            continue
        uri = spotify_search_track(access_token, title, artist)
        if uri:
            # If adding this would exceed playlist max, create next volume first
            if total + len(to_add_uris) + 1 > PLAYLIST_MAX:
                # flush current buffer
                if to_add_uris:
                    if not add_tracks_to_playlist(access_token, current_playlist_id, to_add_uris):
                        logging.error("Failed to flush tracks to playlist. Aborting.")
                        break
                    total += len(to_add_uris)
                    to_add_uris = []
                # create next volume
                current_volume += 1
                current_playlist_id = create_playlist(access_token, current_volume)
                meta["current_volume"] = current_volume
                meta["current_playlist_id"] = current_playlist_id
                save_json(META_FILE, meta)
                total = 0

            to_add_uris.append(uri)
            seen.add(key)
            new_count += 1
        else:
            logging.info("Not found on Spotify: %s — %s", artist, title)
            seen.add(key)  # mark as processed so we don't keep retrying forever

        # flush in batches to avoid big memory usage and keep progress saved
        if len(to_add_uris) >= 50:
            if not add_tracks_to_playlist(access_token, current_playlist_id, to_add_uris):
                logging.error("Failed to add tracks to playlist.")
                break
            total += len(to_add_uris)
            to_add_uris = []
            save_json(SEEN_FILE, list(seen))
            save_json(META_FILE, meta)

    # final flush
    if to_add_uris:
        add_tracks_to_playlist(access_token, current_playlist_id, to_add_uris)

    save_json(SEEN_FILE, list(seen))
    save_json(META_FILE, meta)
    logging.info("Done. Added %d new tracks.", new_count)


if __name__ == "__main__":
    main()
