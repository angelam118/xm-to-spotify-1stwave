import os
import requests
import time
import json
import cloudscraper  # NEW IMPORT: Handles the WAF/403 error

# Read secrets from environment variables
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")

# Constants
XM_CHANNEL = "1stwave"
XM_JSON_FILE = "xmplaylist.json"
MAX_TRACKS_PER_REQUEST = 100
MAX_TRACKS_PER_PLAYLIST = 10000

# --- FIX 1: Correct Spotify API Endpoints ---
def get_access_token():
    # FIXED: Use the official Spotify Accounts URL
    url = "https://accounts.spotify.com/api/token"
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def add_tracks_to_playlist(playlist_id, track_uris):
    if not track_uris:
        return

    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    if len(track_uris) > MAX_TRACKS_PER_PLAYLIST:
        track_uris = track_uris[:MAX_TRACKS_PER_PLAYLIST]
        print(f"Warning: Only adding first {MAX_TRACKS_PER_PLAYLIST} tracks.")

    for chunk in chunked(track_uris, MAX_TRACKS_PER_REQUEST):
        # FIXED: Use the official Spotify API URL
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        
        data = {"uris": chunk}
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code not in [200, 201]:
            print("Error adding tracks:", response.text)
        time.sleep(0.1) 

# --- FIX 2: Use CloudScraper for XMPlaylist ---
def fetch_xmplaylist():
    # Create a scraper instance to bypass Cloudflare/WAF
    scraper = cloudscraper.create_scraper()
    
    url = f"https://xmplaylist.com/api/station/{XM_CHANNEL}"
    
    try:
        # Use scraper.get instead of requests.get
        response = scraper.get(url)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching XMPlaylist: {e}")
        return []

    data = response.json()

    # Save local backup
    with open(XM_JSON_FILE, "w") as f:
        json.dump(data, f, indent=2)

    track_uris = []
    for item in data.get("results", []):
        for link in item.get("links", []):
            if link.get("site") == "spotify":
                # Clean up ID extraction
                raw_url = link["url"]
                # Handle cases like https://open.spotify.com/track/ID?si=...
                if "/track/" in raw_url:
                    track_id = raw_url.split("/track/")[1].split("?")[0]
                    track_uris.append(f"spotify:track:{track_id}")
                break

    return track_uris

if __name__ == "__main__":
    playlist_id = os.getenv("SPOTIFY_PLAYLIST_ID")
    
    print(f"Fetching tracks for channel: {XM_CHANNEL}...")
    xm_tracks = fetch_xmplaylist()
    
    if not xm_tracks:
        print("No tracks fetched from XMPlaylist.")
    else:
        print(f"Fetched {len(xm_tracks)} tracks from XMPlaylist.")
        if playlist_id:
            add_tracks_to_playlist(playlist_id, xm_tracks)
            print("Tracks added to Spotify playlist.")
        else:
            print("No SPOTIFY_PLAYLIST_ID found in env.")
