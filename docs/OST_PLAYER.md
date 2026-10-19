# OST Player

The launcher's Settings → Audio page has a searchable player for the original *Ape Escape* soundtrack.

On startup, the player scans the local OST cache and begins playing a random downloaded track. It continues in shuffle mode, choosing another cached track when each song ends. Startup playback is local-only: it does not query Archive.org or download anything. If no tracks are cached, startup stays silent. Pause and Stop remain respected.

The player reads the track list from the metadata API for [the Internet Archive item](https://archive.org/details/ape-escape-1999-ost) when the player is opened or refreshed. When a user chooses Play, only that track is downloaded into the user's writable application-data folder. The app repo and release archives contain no soundtrack MP3s. Cached tracks and the volume preference survive application updates. The volume slider displays 0–100%; it stores the same preference internally as a 0.0–1.0 audio gain value.

The playback backend uses miniaudio 0.11.22, available under the Unlicense/public-domain dedication or MIT No Attribution license. The Settings UI also links to [Zophar's Domain](https://www.zophar.net/music/playstation-psf/ape-escape) for alternate soundtrack formats and downloads.
