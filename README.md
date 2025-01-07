# moviegoes
![gallery](https://github.com/bertrandclim/moviegoes/blob/main/imgs/hurricane.gif?raw=true)<br>
Python command line utility for making animations from GOES satellite imagery.

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
Replacing `pipx` with `pip` should work too -- `pipx` is just more convenient because it doesn't interact with the base python environment.

## Usage
1. `moviegoes --help`

Arguments to the script specify:
* which GOES data to get (time range, east vs. west, satellite domain, wavelength channel),
* how to turn it into a .mp4 animation (colormap, frames per second, resolution, aspect ratio), and
* where to save the output and where to cache input data. Either create the paths `~/Documents/noaa_data/goes` (cache) and `~/Documents/goes_animations` (output) or specify `--cache` and `--output`.

Included colormaps are all [matplotlib defaults](https://matplotlib.org/stable/users/explain/colors/colormaps.html) as well as their reversed variants by appending `_r` (e.g. `viridis_r` is reversed `viridis`).

## Examples
You can see some cloud movies created with this tool [here](https://drive.google.com/drive/folders/1ala5VyGoitclJU_pgovGzn5MDU8LRa8O?usp=sharing). Some of the commands used for the examples:
* `moviegoes --start "2022-09-04 08:00" --hours 4 --sat EAST --band 16 --colors gist_stern --res native --scale 2`
* `moviegoes --start "2022-07-04 13:00" --hours 24 --sat EAST --band 11 --colors gray_r --res native --scale 2`
