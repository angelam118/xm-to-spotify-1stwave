# XM to Spotify Archiver

This repository implements a serverless automation workflow designed to synchronize broadcast history from **XMPlaylist.com** to **Spotify** playlists.

The solution operates within GitHub Actions, leveraging a scheduled cron job to fetch, parse, and archive track data. It implements robust error handling, WAF evasion techniques, and state management to ensure data integrity and continuous operation without manual intervention.

## Technical Overview

- **WAF Evasion & Request Handling:** Utilizes `cloudscraper` to negotiate Cloudflare's anti-bot protection mechanisms, ensuring reliable access to the XMPlaylist API endpoints which are otherwise restricted by 403 Forbidden errors.

- **Idempotency & Deduplication:** Implements a strict deduplication logic using a persistent local JSON database (`seen_tracks.json`). This ensures that specific Spotify URIs are archived exactly once, regardless of broadcast frequency or script execution overlap.

- **Automated Lifecycle Management:** Monitors the target Spotify playlist size against the API limit (10,000 tracks). Upon approaching this threshold, the system automatically rotates the active playlist, renaming the current iteration to "Vol X" and initializing a new "Vol X+1" container.

- **Fault Tolerance:** Includes exception handling for corrupted or missing state files. The system is designed to self-heal by initializing default states rather than terminating execution, ensuring continuity.

- **Infrastructure:** Deployed on GitHub Actions using public runners, providing a zero-cost execution environment for public repositories.

## Deployment & Configuration

### 1. Repository Initialization

Fork this repository to your own GitHub account to establish an independent workflow context.

### 2. Spotify API Authorization

The application requires valid credentials to authenticate against the Spotify Web API.

1. Navigate to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Create a new Application.
3. Configure a Redirect URI (e.g., `http://example.org/callback`) to facilitate the OAuth flow.
4. Record the Client ID and Client Secret.
5. Generate a Refresh Token: Perform a manual OAuth 2.0 authorization code flow to obtain a long-lived Refresh Token. This token authorizes the application to modify playlists on behalf of the user.

### 3. Environment Secrets Configuration

Securely store the credentials within the repository's GitHub Actions secrets vault. Navigate to **Settings > Secrets and variables > Actions** and provision the following keys:

| Secret Name              | Description |
| ------------------------ | ----------- |
| `SPOTIFY_CLIENT_ID`      | The Client ID provided by the Spotify Dashboard. |
| `SPOTIFY_CLIENT_SECRET`  | The Client Secret provided by the Spotify Dashboard. |
| `SPOTIFY_REFRESH_TOKEN`  | The OAuth 2.0 Refresh Token for the target user account. |

### 4. Application Configuration

Modify `xm_to_spotify.py` to define the target data source. Update the `XML_CHANNEL` constant to match the desired station identifier as defined in the XMPlaylist URL schema.

```python
# Constants
XML_CHANNEL = "1stwave"  # Example: "octone", "lithium", "bpm"```

### 5. Scheduling Strategy

The execution frequency is defined in `.github/workflows/main.yml`. The default configuration executes the synchronization job every 15 minutes to minimize data gaps.

```python
on:
  schedule:
    - cron: '*/15 * * * *'```

### Architecture & File Structure

* `xm_to_spotify.py` - The core application logic. This script handles the HTTP requests to XMPlaylist, parses the HTML/JSON response, performs the deduplication check against the local database, and executes the Spotify API calls.

* `spotify_state.json` - A persistent state file tracking the active playlist_id and the current volume index. This file is committed back to the repository after every run.

* `seen_tracks.json` - A JSON array containing the hash set of all previously archived Spotify URIs. This serves as the primary mechanism for deduplication.

* `.github/workflows/main.yml` - The CI/CD configuration file defining the execution environment, dependency installation, script execution, and git commit operations for state persistence.

### Operational Constraints

* Repository Visibility: GitHub Actions offers unlimited execution minutes for public repositories. Private repositories are subject to monthly quotas (typically 2,000 minutes for free accounts). Given the frequent schedule (every 15 minutes), a private repository may exceed this quota.

* State Reset Procedure: To purge the archive and restart collection:

1. Manually delete the generated playlists within the Spotify application.

2. Clear the contents of `spotify_state.json` (set to `{}`) and `seen_tracks.json` (set to `[]`) within the repository.

3. The next execution cycle will detect the void state and initialize "Vol 1".
