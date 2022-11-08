# ReSpotGUI

![](https://raw.githubusercontent.com/digfish/respotgui/master/respotgui.png)

The purpose is to provide a graphical frontend for the [librespot-java](https://github.com/librespot-org/librespot-java), a library that provides streaming and support for Spotify Connect devices. 

# Features
- Search for any kind of item in spotify (artist, playlist, track names, albums)
- Volume control
- Play controls
- Seek to any time point in the track
- Able to choose any track in the playlist

# Requirements

- A Spotify premium subscription
- Java installed
- librespot-java (last version can be obtained [here](https://github.com/librespot-org/librespot-java/releases))[^1]
- Python 3 installed (of course!)

# Install

To install type:

```
pip install respotgui
```

to execute:
```
python -m respot.gui
```
or simply:
```
respotgui
```

[^1]: Download the file `librespot-api-*.jar` and execute it with `java -jar`

# Changelog

- updated screenshot
- Tabs are now restored at start
- Implemented playlists in tabs
- Added buttons for change the repeat and shuffle.
- Changed font to Verdana and implemented buttons
- Search results in a tree, cleaned code
- Now listens to presses on media keys
- Added slider for volume
- added total time in timer and made improvements
- Implemented search for playlists and listbox with active playlist
- Minor changes to the gui. Removed thread timers
- minor fixes to the gui
- synced with the project in pypi
- Minor corrections to allow a stable install
- image files relative to the source dir
- Updated definition files
- Delete respogui-0+unknown directory
- first commit
