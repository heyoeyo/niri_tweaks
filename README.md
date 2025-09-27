# niri tweaks

This repo holds some basic helper scripts that are used to modify the behavior of the [niri](https://github.com/YaLTeR/niri) wayland compositor.

## niri_tile_to_n.py

This script makes niri behave more like a 'regular' tiling window manager up to the point of having 'N' windows (where N is adjustable, 3 by default), after which windows will be added in the normal scrolling pattern. It uses the [niri IPC](https://github.com/YaLTeR/niri/wiki/IPC) and is only tested on niri version 25.08 so far.

### Example

The example below shows the sequence of opening 4 windows, when 'N=3'. The first opened window (A) will be maximized:
```
┌─────────────┐
│             │
│      A      │
│             │
│             │
└─────────────┘
```

Opening a second window (B) will collapse (A) so the windows tile:
```
┌─────┐ ┌─────┐
│     │ │     │
│  A  │ │  B  │
│     │ │     │
│     │ │     │
└─────┘ └─────┘
```

Opening a third window (C) will begin stacking windows on the right:
```
┌─────┐ ┌─────┐
│     │ │  B  │
│  A  │ └─────┘
│     │ ┌─────┐
│     │ │  C  │
└─────┘ └─────┘
```

The fourth window (D), opens off-screen in the normal niri scrolling pattern:
```
┌─────┐ ┌─────┐ ┌─────┐
│     │ │  B  │ │     │
│  A  │ └─────┘ │  D  │
│     │ ┌─────┐ │     │
│     │ │  C  │ │     │
└─────┘ └─────┘ └─────┘
```

Any other windows opened will continue to be added to the right.

### Quick test run

If you'd like to quickly try this out, use the following terminal command:
```bash
curl https://raw.githubusercontent.com/heyoeyo/niri_tweaks/refs/heads/main/niri_tile_to_n.py | python3
```
This downloads the script text and pipes it straight into python to run it. After doing this, try opening 3 or more windows to see the effect. Hitting ctrl+c or closing the terminal will disable the effect.

### Permanent use

To have the script always running, either clone this repo, or otherwise copy the contents of [the script](https://github.com/heyoeyo/niri_tweaks/blob/main/niri_tile_to_n.py) into a file somewhere on your machine. Then you just need to update your [niri config file](https://github.com/YaLTeR/niri/wiki/Configuration:-Introduction) (usually in `~/.config/niri/config.kdl`) to run the script on start-up:
```bash
spawn-at-startup "python3" "/path/to/niri_tile_to_n.py"
```

You'll have to log-out/log-in for this to take effect.

### Customization

There are a few flags for toggling features (like `-x` for disabling auto-maximization of new windows) which can be found by running:
```bash
python3 niri_tile_to_n.py --help
```

The script itself is one big (ugly) python file, but should be easy to edit if you want more specific customizations. Most of the script is dedicated to listening to the niri IPC, while the [last 50 lines](https://github.com/heyoeyo/niri_tweaks/blob/d4f64bf4d79407f3cb70283392aadfb96aa240ff/niri_tile_to_n.py#L522-L568) or so hold all of the custom windowing logic (so hack away here if you want some more custom behavior).

## niri_spawn_or_jump.py

This script acts as an alternative to the `spawn` command in niri. It can be used to spawn an application, but if the application is already open it will jump to the existing instance. If there are multiple instances, then it will cycle between them. By default this works across all workspaces and for both floating and tiled windows, though this can be adjusted with flags. To see a list of available modifier flags, run:

```bash
python3 /path/to/niri_spawn_or_jump.py --help
```

### Usage

To bind to a keypress, you need to add a line to the niri config, like:

```bash
Mod+T { spawn "python3" "/path/to/niri_spawn_or_jump.py" "alacritty"; }
```

This also works for flatpaks:

```bash
Mod+B { spawn "python3" "/path/to/niri_spawn_or_jump.py" "flatpak run app.zen_browser.app"; }
```
By default, this will search for existing instances based on the `app-id` that niri assigns, assuming this matches the name used to run the application (e.g. `alacritty` or `app.zen_browser.app`). Some applications seem to use a different name, like the flatpak for Chromium, which has an `app-id` of `chromium-browser`. For these applications, the `app-id` can be passed as a second argument:

```bash
Mod+B { spawn "python3" "/path/to/niri_spawn_or_jump.py" "flatpak run org.chromium.Chromium" "chromium-browser"; }
```

To help figure out the `app-id` for these sorts of applications, run this script without any arguments. The `app-id` of the currently focused window will then be printed out in the terminal.


## fuzzel_helper.sh

The normal behavior of the niri application launcher ([fuzzel](https://codeberg.org/dnkl/fuzzel)) is to only open when launched. This script makes it toggle on/off, so that a single command can be used to both open and close (i.e. cancel), which seems more intuitive.

### Usage

You need to add (or most likely [replace](https://github.com/YaLTeR/niri/blob/e837e39623457dc5ad29c34a5ce4d4616e5fbf1e/resources/default-config.kdl#L366)) a keybinding in the niri config file to run this script, for example:
```bash
Mod+0 repeat=false { spawn "bash" "/path/to/fuzzel_helper.sh"; }
```

This makes the combo 'Mod+0' open the launcher or close it if it's already open.

### Use Super (only) to open launcher

Following niri [issue #605](https://github.com/YaLTeR/niri/issues/605#issuecomment-2600315134), it's possible to use [keyd](https://github.com/rvaiya/keyd) to launch from tapping just the Super key.
The following keyd config maps 'tapping Super' to be equivalent to 'Super+0', along with some other useful mappings:

<details>

<summary>/etc/keyd/keyd.conf</summary>

```ini
[ids]

# This seems to provide a way to match to different inputs (* matches to all)
# To find ids, can press keys after using: sudo keyd monitor
# Seems able to catch non-keyboard events too...?
*


[global]

# Max milliseconds before ignoring key release
overload_tap_timeout = 300;


[main]

# Make super key tap act like a super+key combo
leftmeta = overload(meta, macro(leftmeta+0))
# Overload syntax seems to be:
#   key_being_altered = overload(behavior when held, behavior when tapped)

# Make the 'right menu' key act like the super key
compose = overload(meta, macro(leftmeta+0))

# Make insert key act like the escape key
insert = esc
```
</details>


## swaybg_helper.sh

This script uses [swaybg](https://github.com/swaywm/swaybg), to set a background wallpaper, while also providing support for cycling wallpapers (which swaybg doesn't do by default). It works by loading the 'most recently accessed' file in a given folder (and will use `touch` to update the oldest-accessed file to implement cycling).

### Usage

The script has 4 optional flags: `--folder`, `--cycle`, `--delay` and `--notify`. Each of these has a single-letter (e.g. `-f`, `-c`) version as well.

Using `--folder /path/to/folder`  will change the folder location from which wallpaper images are loaded. If this isn't provided, the script defaults to `~/Pictures/Wallpapers`. The `--cycle` flag is used to load a different image and `--delay` can be added to introduce a short delay before closing the previous swaybg instance. This isn't mandatory, but without it there can be a brief blank background before the next image loads otherwise. The `--notify` flag will trigger notifications on background change.

#### Load wallpaper on start-up

To have this script set a wallpaper on startup, first make sure swaybg is installed, then add the following line to your niri config:
```bash
spawn-at-startup "bash" "/path/to/swaybg_helper.sh" "-f" "/path/to/wallpapers/folder"
```

The `-f` flag can be ommited if images are placed in `~/Pictures/Wallpapers`. Adding the `-c` flag will result in the wallpaper changing on each login.

#### Cycle wallpaper on keypress

To cycle backgrounds on a keypress, add the following keybind:
```bash
Mod+Shift+W { spawn "bash" "/path/to/swaybg_helper.sh" "-c" "-d" "-f" "/path/to/wallpapers/folder"; }
```

Again, `-f` can be omitted as can `-d` if having a delay isn't a concern.