import os
import requests
import time

# Read secrets from environment variables
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")

# Spotify API constants
MAX_TRACKS_PER_REQUEST = 100
MAX_TRACKS_PER_PLAYLIST = 10000

def get_access_token():
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
    """Yield successive chunks of size `size` from iterable"""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def add_tracks_to_playlist(playlist_id, track_uris):
    access_token = get_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}

    # Respect Spotify 10k max per playlist
    if len(track_uris) > MAX_TRACKS_PER_PLAYLIST:
        track_uris = track_uris[:MAX_TRACKS_PER_PLAYLIST]
        print(f"Warning: Only adding first {MAX_TRACKS_PER_PLAYLIST} tracks due to Spotify limit.")

    for chunk in chunked(track_uris, MAX_TRACKS_PER_REQUEST):
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        data = {"uris": chunk}
        response = requests.post(url, json=data, headers=headers)
        if response.status_code not in [200, 201]:
            print("Error adding tracks:", response.json())
        time.sleep(0.1)  # small delay to avoid rate limits
