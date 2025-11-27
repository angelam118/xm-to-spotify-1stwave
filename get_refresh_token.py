import requests
from urllib.parse import urlparse, parse_qs
import json
import os

# ---------------- CONFIG ----------------
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Must match the redirect URI you registered in Spotify dashboard
REDIRECT_URI = "https://example.com/callback"

# Scopes needed to manage playlists
SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private"

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# ---------------- Step 1: Generate auth URL ----------------
def generate_auth_url():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES
    }
    url = AUTH_URL + "?" + "&".join([f"{k}={requests.utils.quote(v)}" for k, v in params.items()])
    print("\nOpen this URL in your browser, log in, and authorize the app:\n")
    print(url)
    print("\nAfter authorizing, Spotify will redirect you to something like:")
    print("https://example.com/callback?code=AUTH_CODE_HERE")
    print("Copy the full URL from your browser and paste it below.\n")

# ---------------- Step 2: Exchange code for tokens ----------------
def exchange_code_for_token(code):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    r = requests.post(TOKEN_URL, data=data)
    r.raise_for_status()
    tokens = r.json()
    print("\n=== TOKENS RECEIVED ===")
    print(json.dumps(tokens, indent=4))

    # Save tokens locally
    with open("spotify_tokens.json", "w") as f:
        json.dump(tokens, f, indent=4)

    print("\nSaved tokens to spotify_tokens.json. Keep this file secure!\n")

# ---------------- Main ----------------
if __name__ == "__main__":
    generate_auth_url()
    redirect_url = input("Paste the full redirect URL here: ").strip()
    parsed = urlparse(redirect_url)
    code = parse_qs(parsed.query).get("code")
    if not code:
        print("No code found in URL. Please copy the full redirect URL exactly.")
        exit(1)
    code = code[0]
    exchange_code_for_token(code)
