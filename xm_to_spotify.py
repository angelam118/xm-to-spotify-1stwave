import os
import requests

SPOTIFY_USER_ID = os.environ['SPOTIFY_USER_ID']
SPOTIFY_ACCESS_TOKEN = os.environ['SPOTIFY_ACCESS_TOKEN']
BASE_URL = "https://api.spotify.com/v1"

HEADERS = {
    "Authorization": f"Bearer {SPOTIFY_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def get_playlist_track_count(playlist_id):
    url = f"{BASE_URL}/playlists/{playlist_id}/tracks?limit=1"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()['total']

def create_playlist(name, description=""):
    url = f"{BASE_URL}/users/{SPOTIFY_USER_ID}/playlists"
    data = {
        "name": name,
        "description": description,
        "public": False
    }
    response = requests.post(url, headers=HEADERS, json=data)
    response.raise_for_status()
    return response.json()['id']

def add_tracks_to_playlist(playlist_id, track_uris):
    BATCH_SIZE = 100  # max per request
    for i in range(0, len(track_uris), BATCH_SIZE):
        batch = track_uris[i:i+BATCH_SIZE]
        url = f"{BASE_URL}/playlists/{playlist_id}/tracks"
        data = {"uris": batch}
        response = requests.post(url, headers=HEADERS, json=data)
        response.raise_for_status()

def distribute_tracks_across_playlists(base_name, track_uris):
    playlist_index = 1
    current_playlist_id = create_playlist(f"{base_name} Part {playlist_index}")

    while track_uris:
        current_count = get_playlist_track_count(current_playlist_id)
        space_left = 10000 - current_count
        to_add = track_uris[:space_left]
        add_tracks_to_playlist(current_playlist_id, to_add)
        track_uris = track_uris[space_left:]

        if track_uris:  # need new playlist
            playlist_index += 1
            current_playlist_id = create_playlist(f"{base_name} Part {playlist_index}")

