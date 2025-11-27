# XM to Spotify Archiver

A serverless bot that scrapes radio history from **XMPlaylist.com** and archives it to **Spotify** automatically.

It runs entirely on GitHub Actions using a cron schedule. It handles the scraping, bypasses Cloudflare checks, and manages the playlist size so you don't have to touch it.

## Technical Overview

- **Bypassing Cloudflare:** Uses `cloudscraper` to handle the anti-bot checks. Regular requests usually get hit with a 403 Forbidden, but this handles the JS challenge automatically.

- **No Duplicates:** Keeps a local database (`seen_tracks.json`) of every song ID it has ever verified. It checks this before adding anything to Spotify, so even if the station plays "Bohemian Rhapsody" three times a day, you only get it once.

- **Auto-Rotation:** Spotify caps playlists at 10,000 songs. This script watches the count; when it hits the limit (9,900 buffer), it renames the old playlist to "Vol X" and starts a fresh "Vol X+1" automatically.

- **Self-Healing:** If the state files (JSON) ever get empty or corrupted, the script detects it and resets to a default state instead of crashing.

- **Infrastructure:** Runs on GitHub Actions. If the repo is public, this is completely free.

## Deployment & Configuration

### 1. Fork the Repo

Fork this repository to your own account so you can run your own workflows.

### 2. Get Spotify Keys

You need a Spotify App to use the API.

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Create an App.
3. Set the Redirect URI to `http://example.org/callback`.
4. Copy the **Client ID** and **Client Secret**.
5. **Get the Refresh Token:** You'll need to run a manual OAuth flow once to get a long-lived Refresh Token. This allows the bot to modify your playlists forever without you logging in again.

### 3. Add Secrets

Go to your repository **Settings > Secrets and variables > Actions** and add these three keys:

| Secret Name | Description |
| :--- | :--- |
| `SPOTIFY_CLIENT_ID` | From your Spotify Dashboard. |
| `SPOTIFY_CLIENT_SECRET` | From your Spotify Dashboard. |
| `SPOTIFY_REFRESH_TOKEN` | The long token string you generated. |

### 4. Configure the Station

Open `xm_to_spotify.py` and change the `XM_CHANNEL` variable to match the station you want (check the URL on xmplaylist.com to be sure).

```
# Constants
XM_CHANNEL = "1stwave"  # Example: "octane", "lithium", "bpm"
```

### **5. Schedule **

The schedule is in `.github/workflows/main.yml`. By default, it runs every 15 minutes to catch songs before they fall off the recent history list.

```
on:
  schedule:
    - cron: '*/15 * * * *'
```

### **Architecture & File Structure**

* `xm_to_spotify.py` - The main script. Handles the scraping, parsing, deduplication logic, and talks to the Spotify API.

* `spotify_state.json` - Keeps track of the current Playlist ID and which "Volume" number we are on. The workflow commits this back to the repo after every run.

* `seen_tracks.json` - A JSON list of every Spotify URI we've already archived. Used to prevent duplicates.

* `.github/workflows/main.yml` - The GitHub Actions config. Installs Python, runs the script, and saves the JSON files.

### **Operational Constraints**

- **Keep It Public:** GitHub Actions are free and unlimited for public repos. If you make this private, you have a monthly limit (usually 2,000 minutes). Since this runs every 15 mins, a private repo will hit that limit pretty fast.

- **How To Reset:** If you want to nuke everything and start fresh:

   1. Delete the playlists in your Spotify App.

   2. Clear the contents of `spotify_state.json` (set to `{}`) and `seen_tracks.json` (set to `[]`) within the repository.

   3. The next run will see the empty state and start over at "Vol 1".
