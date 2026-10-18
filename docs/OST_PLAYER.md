# OST Player

The launcher's Settings page has a searchable player for the original *Ape Escape* soundtrack.

The player reads the track list from the metadata API for [the Internet Archive item](https://archive.org/details/ape-escape-1999-ost). When a user chooses Play, only that track is downloaded into the user's writable application-data folder. The app repo and release archives contain no soundtrack MP3s. Cached tracks and the volume preference survive application updates.

The playback backend uses miniaudio 0.11.22, available under the Unlicense/public-domain dedication or MIT No Attribution license. The Settings UI also links to [Zophar's Domain](https://www.zophar.net/music/playstation-psf/ape-escape) for alternate soundtrack formats and downloads.
