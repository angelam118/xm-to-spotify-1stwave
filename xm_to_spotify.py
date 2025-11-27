import os
import requests
import time
import json
import cloudscraper

# --- CONFIGURATION ---
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")

# Files
XM_JSON_FILE = "xmplaylist.json"
STATE_FILE = "spotify_state.json" 
SEEN_TRACKS_FILE = "seen_tracks.json" # NEW: Database of all unique song IDs

# Constants
XM_CHANNEL = "1stwave"
PLAYLIST_BASE_NAME = f"XM {XM_CHANNEL} Unique Collection"
MAX_TRACKS_PER_REQUEST = 100
PLAYLIST_LIMIT = 9900 

# --- AUTHENTICATION ---
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

def get_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# --- SPOTIFY HELPERS ---
def get_user_id(token):
    url = "https://api.spotify.com/v1/me"
    response = requests.get(url, headers=get_headers(token))
    response.raise_for_status()
    return response.json()["id"]

def get_playlist_size(token, playlist_id):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    response = requests.get(url, headers=get_headers(token))
    if response.status_code == 404: return None
    response.raise_for_status()
    return response.json()["tracks"]["total"]

def create_playlist(token, user_id, name):
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    data = {"name": name, "public": False, "description": "Auto-generated unique tracks from XM"}
    response = requests.post(url, headers=get_headers(token), json=data)
    response.raise_for_status()
    return response.json()["id"]

def rename_playlist(token, playlist_id, new_name):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    requests.put(url, headers=get_headers(token), json={"name": new_name})

def add_tracks(token, playlist_id, track_uris):
    if not track_uris: return
    for i in range(0, len(track_uris), MAX_TRACKS_PER_REQUEST):
        chunk = track_uris[i:i + MAX_TRACKS_PER_REQUEST]
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        requests.post(url, headers=get_headers(token), json={"uris": chunk})
        time.sleep(0.5)

# --- STATE & DATABASE MANAGEMENT ---
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"playlist_id": None, "volume": 1}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_seen_tracks():
    if os.path.exists(SEEN_TRACKS_FILE):
        with open(SEEN_TRACKS_FILE, "r") as f:
            # We use a set() for super fast lookups
            return set(json.load(f))
    return set()

def save_seen_tracks(seen_set):
    with open(SEEN_TRACKS_FILE, "w") as f:
        # Convert set back to list for JSON
        json.dump(list(seen_set), f)

# --- XM FETCHING ---
def fetch_xm_tracks():
    scraper = cloudscraper.create_scraper()
    try:
        url = f"https://xmplaylist.com/api/station/{XM_CHANNEL}"
        resp = scraper.get(url)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching XM: {e}")
        return []

    uris = []
    # Loop over results 
    # API sends [Newest -> Oldest]. We want to process Oldest -> Newest
    results = data.get("results") or []
    
    # Reverse here so we process historical order
    for item in reversed(results):
        links = item.get("links") or []
        for link in links:
            if isinstance(link, dict) and link.get("site") == "spotify":
                if "url" in link and "/track/" in link["url"]:
                    try:
                        tid = link["url"].split("/track/")[1].split("?")[0]
                        uris.append(f"spotify:track:{tid}")
                    except IndexError: pass
                break
    return uris

# --- MAIN LOGIC ---
if __name__ == "__main__":
    print(f"Starting Unique Sync for {XM_CHANNEL}...")
    token = get_access_token()
    state = load_state()
    seen_tracks = load_seen_tracks() # Load the database of songs we already have
    
    current_id = state.get("playlist_id")
    current_vol = state.get("volume", 1)

    # 1. ROTATION LOGIC
    need_new_playlist = False
    if not current_id:
        need_new_playlist = True
    else:
        size = get_playlist_size(token, current_id)
        if size is None:
            print("Playlist missing. Creating new.")
            need_new_playlist = True
        elif size >= PLAYLIST_LIMIT:
            print(f"Volume {current_vol} Full. Rotating...")
            rename_playlist(token, current_id, f"{PLAYLIST_BASE_NAME} - Vol {current_vol}")
            current_vol += 1
            need_new_playlist = True
    
    if need_new_playlist:
        user_id = get_user_id(token)
        new_name = f"{PLAYLIST_BASE_NAME} - Vol {current_vol} (Current)"
        current_id = create_playlist(token, user_id, new_name)
        state["playlist_id"] = current_id
        state["volume"] = current_vol
        save_state(state)

    # 2. FETCH & UNIQUE FILTER
    fetched_tracks = fetch_xm_tracks()
    tracks_to_add = []
    
    if not fetched_tracks:
        print("No tracks fetched from API.")
    else:
        print(f"Fetched {len(fetched_tracks)} recent tracks from radio.")
        for uri in fetched_tracks:
            # THIS IS THE KEY CHANGE:
            if uri not in seen_tracks:
                tracks_to_add.append(uri)
                seen_tracks.add(uri) # Add to memory immediately so we don't add duplicates within the same batch
            else:
                # Optional: Print duplicate skipping
                # print(f"Skipping duplicate: {uri}")
                pass

    # 3. ADD TO SPOTIFY
    if tracks_to_add:
        print(f"Adding {len(tracks_to_add)} NEW unique tracks...")
        add_tracks(token, current_id, tracks_to_add)
        
        # Save the updated database
        save_seen_tracks(seen_tracks)
        print("Success. Database updated.")
    else:
        print("No new unique tracks found.")
