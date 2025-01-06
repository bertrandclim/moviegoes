Python package for making animations from GOES satellite imagery.

## Dependencies
Python library dependencies are handled automatically by pip/pipx/etc. An additional dependency (`ffmpeg`) __must be installed manually__.

## Installation
1. `brew install ffmpeg` (mac) or e.g. `apt-get ffmpeg` (linux)
2. `brew install pipx` (mac) or e.g. `apt-get pipx` (linux)
3. `pipx install git+https://github.com/bertrandclim/moviegoes.git`

If the pipx install succeeded, you should see something like
```
These apps are now globally available
— moviegoes
done! ✨ 🌟 ✨
```

## Usage
1. `moviegoes --help`

Arguments to the script specify which GOES data to get (time range, east vs. west, satellite domain, wavelength channel) and how to turn it into a .mp4 animation (colormap, frames per second, resolution, aspect ratio). Included colormaps are all [matplotlib defaults](https://matplotlib.org/stable/users/explain/colors/colormaps.html) as well as their reversed variants by appending `_r` (e.g. `viridis_r` is reversed `viridis`).
