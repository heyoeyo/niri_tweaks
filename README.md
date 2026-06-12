# niri tweaks

This repo holds some basic helper scripts that can be used to modify the behavior of the [niri](https://github.com/YaLTeR/niri) wayland compositor. The scripts are all independent of one another, so any one can be used without needing the others.

#### Scripts:
- [niri_tile_to_n.py](#niri_tile_to_npy)
- [niri_spawnjump.py](#niri_spawnjumppy)
- [niri_window_details.sh](#niri_window_detailssh)
- [niri_workspace_helper.py](#niri_workspace_helperpy)
- [niri_peekaboo.py](#niri_peekaboopy)
- [niri_overview_bind.py](#niri_overview_bindpy)
- [niri_parse_keybinds.py](#niri_parse_keybindspy)
- [niri_search_window.py](#niri_search_windowpy)
- [fuzzel_helper.sh](#fuzzel_helpersh)
- [swaybg_helper.sh](#swaybg_helpersh)
- [mute_on_startup.sh](#mute_on_startupsh)


## niri_tile_to_n.py

This script makes niri behave more like a 'regular' tiling window manager up to the point of having 'N' windows (where N is adjustable, 3 by default), after which windows will be added in the normal scrolling pattern. It uses the [niri IPC](https://github.com/YaLTeR/niri/wiki/IPC) and requires niri version 25.08 or greater.

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
```kdl
spawn-at-startup "python3" "/path/to/niri_tile_to_n.py"
```

You'll have to log-out/log-in for this to take effect.

### Customization

There are a few flags for toggling features (like `-x` for disabling auto-maximization of new windows) which can be found by running:
```bash
python3 niri_tile_to_n.py --help
```

The script itself is one big (ugly) python file, but should be easy to edit if you want more specific customizations. Most of the script is dedicated to listening to the niri IPC, while the [last 50 lines](https://github.com/heyoeyo/niri_tweaks/blob/d4f64bf4d79407f3cb70283392aadfb96aa240ff/niri_tile_to_n.py#L522-L568) or so hold all of the custom windowing logic (so hack away here if you want some more custom behavior).

<br>

## niri_spawnjump.py

This script acts as an alternative to the `spawn` command in niri. It can be used to spawn an application, but if the application is already open it will jump to the existing instance. If there are multiple instances, then it will cycle between them. By default this works across all workspaces and for both floating and tiled windows, though this can be adjusted with flags. To see a list of available modifier flags, run:

```bash
python3 /path/to/niri_spawnjump.py --help
```

For example, `-w` will cause jump/cycling behavior to only search on the current workspace, which has the effect of creating one instance per workspace. The `-l` flag can be used to set a spawn limit >1, for example `-l 3` would allow three instances to be spawned before jumping/cycling between them. If having a window limit is sometimes a problem, the `-o` flag can be set which allows for unconditionally spawning windows when the overview is open.

As an alternative to cycling, the `-p` and `-s` flags can be used to 'pull' and 'push' (respectively) an existing instance instead of jumping to it. This results in behavior similar to the ability to _minimize_ a window from more conventional windowing systems. This seems to make sense for binding to a file explorer, for example.

### Usage

To bind to a keypress, you need to add a line to the niri config. Flags for the script can be added at the end, like:

```kdl
Mod+T { spawn "python3" "/path/to/niri_spawnjump.py" "alacritty" "-w" "-p" "-s"; }
```

For flatpaks, use the entire run command:

```kdl
Mod+B { spawn "python3" "/path/to/niri_spawnjump.py" "flatpak run app.zen_browser.app"; }
```
By default, this will search for existing instances based on the `app-id` that niri assigns, assuming this matches the name used to run the application (e.g. `alacritty` or `app.zen_browser.app`). Some applications seem to use a different name, like the flatpak for Chromium, which has an `app-id` of `chromium-browser`. For these applications, the `app-id` can be passed as a second argument:

```kdl
Mod+B { spawn "python3" "/path/to/niri_spawnjump.py" "flatpak run org.chromium.Chromium" "chromium-browser"; }
```

To help figure out the `app-id` for these sorts of applications, run this script without any arguments. The `app-id` of the currently focused window will then be printed out in the terminal.

### Scratchpad

The script includes support for providing a 'scratchpad' workspace name (use `-t workspacename`), this will auto-enable `--push` and `--pull` and will push windows to the provided workspace name, instead of pushing them to the end of the current workspace:

```kdl
Mod+T { spawn "python3" "/path/to/niri_spawnjump.py" "alacritty" "-t" "scratch"; }
```

Your niri config needs to include a line like: `workspace "scratch"` for this command to work properly.


<br>

## niri_window_details.sh

This script is mostly used for debugging. It prints out basic window information from calling `niri msg focused-window` into a notification. For example, this can print out the `app-id` of a window, making it useful for setting up window rules.

A keybinding can be added to the niri config file to trigger this:
```kdl
Mod+Backslash repeat=false { spawn "bash" "/path/to/niri_window_details.sh"; }
```

Pressing this keybinding while focusing a window will give you a notification that includes basic information about that window. It's also easy to modify the script to print out other info if needed.


<br>

## niri_workspace_helper.py

This script augments both the `focus-workspace` and `focus-workspace-up/down` commands. When replacing the `focus-workspace` command (normally bound to `Mod+1`, `Mod+2` etc.) it behaves like the original command to move between workspaces, but when already on the focused workspace, will instead toggle the niri overview.

When replacing the `focus-workspace-up/down` commands, this script can be made to skip over empty workspaces or marked (e.g. hidden) workspaces as well as handle wrap-around. It can also act as a `focus-first/last` command.

To use this script, replace the existing [focus-workspace](https://github.com/YaLTeR/niri/blob/2776005c5fc4fbb85636672213b8b84a319dfb01/resources/default-config.kdl#L516-L524) keybinds with a call to this script followed by a workspace index or name, for example:
```kdl
Mod+1 { spawn-sh "python3 /path/to/niri_workspace_helper.py 1"; }
```

As an alternative to toggling the overview, the `--jump` or `-j` flag can be added to instead jump to the first or last column of the workspace (when already on the focused workspace). This removes the need for dedicated [Mod+Home/Mod+End](https://github.com/YaLTeR/niri/blob/e837e39623457dc5ad29c34a5ce4d4616e5fbf1e/resources/default-config.kdl#L427-L428) keybinds, for example.

To instead cycle through workspaces, provide a keyword of `up`, `down`, `first` or `last` instead of an index. To skip empty workspaces use `-s`. To _always_ skip specific workspaces (even if not empty), list them after the `--hidden` (or `-z`) flag, for example:
```kdl
// Up/down
Mod+apostrophe { spawn-sh "python3 /path/to/niri_workspace_helper.py down -ws --hidden scratch"; }
Mod+semicolon { spawn-sh "python3 /path/to/niri_workspace_helper.py up -ws -z scratch"; }

// First/last
Mod+grave { spawn-sh "python3 /path/to/niri_workspace_helper.py first -s"; }
Mod+backspace { spawn-sh "python3 /path/to/niri_workspace_helper.py last -s"; }
```

More information about the flags can be found by running the script directly (in a terminal) with `--help`:
```bash
python3 /path/to/niri_workspace_helper.py --help
```


<br>

## niri_peekaboo.py

<p align="center">
  <img src="https://github.com/user-attachments/assets/f3824bd1-b240-4146-a8f2-6de68c4a5aa9" style="height:240px">
</p>

This is an experimental script used to pull nearby windows into view as floats for quick interactions, without needing to scroll the view. This is meant for use on maximized or fullscreen windows. Non-full-width windows won't work as expected and may require some IPC updates before they can be properly supported.

The script can be bound to a keypress in your niri config:
```kdl
Mod+P { spawn "python3" "/path/to/niri_peekaboo.py"; }
```

Running this command once will float window(s) in the column to the right of where you're focused and move the window(s) into view on the left. Running it again will return the floating windows back to the column on the right (e.g. offscreen).

There are several configuration options which can be viewed by running (in a terminal):
```bash
python3 /path/to/niri_peekaboo.py --help
```


<br>

## niri_overview_bind.py

This is a very simple script, inspired by a post on the niri issue board ([#2842](https://github.com/YaLTeR/niri/discussions/2842)) about setting up different keybinds in overview mode. The general script usage is:

```bash
niri_overview_bind.sh 'command in overview mode' 'command in normal mode'
```


 For example, an intuitive use of this is to re-use the shortcuts normally used to [move windows around](https://github.com/YaLTeR/niri/blob/54c7fdcd1adcfade596aca1070062f3f0fb5d4d0/resources/default-config.kdl#L412-L419) to move _workspaces_ when in overview mode. This can be done as follows:

```kdl
Mod+Ctrl+Down { spawn-sh "bash /path/to/niri_overview_bind.sh 'move-workspace-down' 'move-window-down-or-to-workspace-down'"; }
```

This removes the need for remembering [dedicated keybinds](https://github.com/YaLTeR/niri/blob/54c7fdcd1adcfade596aca1070062f3f0fb5d4d0/resources/default-config.kdl#L472-L475) for moving workspaces!


<br>

## niri_parse_keybinds.py

<p align="center">
  <img src="https://github.com/user-attachments/assets/45f4eecd-ae60-46f3-923a-a2d7b36800b6" style="height:320px">
</p>

This script is meant to help replace the built-in hotkey overlay. It can be used to parse niri keybinds into a 'dmenu' format, to make them searchable in fuzzel (or even [fzf](https://github.com/junegunn/fzf)). To avoid requiring dependencies, this script tries to parse the kdl file without any libraries, which may be error prone! Feel free to open an issue if you find any problems.

The output of this script can be piped into fuzzel to make it searchable, for example:

```kdl
Mod+Slash { spawn-sh "python3 /path/to/niri_parse_keybinds.py | fuzzel -d -w 100 -f monospace --match-mode exact"; }
```

This keybind will launch fuzzel with a list of searchable keybinds (only the `-d` flag is needed on fuzzel, the others are nice to have). By default, the script will search for keybinds in `~/.config/niri/config.kdl`, a different file path can be given with the `-i` flag. For now, the script assumes you have only 1 `binds {...}` section and does _not_ follow 'include' directives.

For faster/less error-prone parsing, it can be helpful to split your `binds {...}` into a separate kdl file, using the new (v25.11) config [include](https://yalter.github.io/niri/Configuration%3A-Include.html) functionality of niri, though you will need to provide the `-i /path/to/keybinds.kdl` flag in this case.

Also worth noting: the call to fuzzel can be replaced with the [fuzzel helper](https://github.com/heyoeyo/niri_tweaks?tab=readme-ov-file#fuzzel_helpersh) script so that the fuzzy-find search is toggled on/off with the same keybind.

<br>

## niri_search_window.py

This script acts as a text-based alternative to built-in 'alt-tab' functionality. When called it uses [fuzzel](https://codeberg.org/dnkl/fuzzel) to fuzzy search all Niri windows. Once a window is selected Niri will switch to it.

```kdl
Alt+Tab { spawn-sh "python3 /path/to/niri_search_window.py"; }
```

Note that the built-in graphical alt-tab functionality is available on both `Alt+Tab` and `Mod+Tab`, so it's possible to replace one shortcut with this script while keeping the built-in option on the other.

<br>

## fuzzel_helper.sh

The normal behavior of the niri application launcher ([fuzzel](https://codeberg.org/dnkl/fuzzel)) is to only open when launched. This script makes it toggle on/off, so that a single command can be used to both open and close (i.e. cancel), which seems more intuitive.

### Usage

You need to add (or most likely [replace](https://github.com/YaLTeR/niri/blob/e837e39623457dc5ad29c34a5ce4d4616e5fbf1e/resources/default-config.kdl#L366)) a keybinding in the niri config file to run this script, for example:
```kdl
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

# Holding a key for longer than this (in ms) won't count as a tap
overload_tap_timeout = 300;

[main]

# Make super key tap act like a super+0 combo
leftmeta = overload(meta, macro(leftmeta+0))
# Syntax seems to be:
#   key_being_altered = overload(behavior when held, behavior when tapped)

# Make the 'right menu' key act like the super key
compose = overload(meta, macro(leftmeta+0))
```
</details>


<br>

## swaybg_helper.sh

This script uses [swaybg](https://github.com/swaywm/swaybg) to set a background wallpaper while also providing support for cycling wallpapers (which swaybg doesn't do by default). It works by loading the 'most recently accessed' file in a given folder (and will use `touch` to update the oldest-accessed file to implement cycling).

### Usage

The script has 4 optional flags: `--folder`, `--cycle`, `--delay` and `--notify`. Each of these has a single-letter (e.g. `-f`, `-c`) version as well.

Using `--folder /path/to/folder`  will change the folder location from which wallpaper images are loaded. If this isn't provided, the script defaults to `~/Pictures/Wallpapers`. The `--cycle` flag is used to load a different image and `--delay` can be added to introduce a short delay before closing the previous swaybg instance. This isn't mandatory, but without it there can be a brief blank background before the next image loads otherwise. The `--notify` flag will trigger notifications on background change.

#### Load wallpaper on start-up

To have this script set a wallpaper on startup, first make sure swaybg is installed, then add the following line to your niri config:
```kdl
spawn-at-startup "bash" "/path/to/swaybg_helper.sh" "-f" "/path/to/wallpapers/folder"
```

The `-f` flag can be ommited if images are placed in `~/Pictures/Wallpapers`. Adding the `-c` flag will result in the wallpaper changing on each login.

#### Cycle wallpaper on keypress

To cycle backgrounds on a keypress, add the following keybind:
```kdl
Mod+Shift+W { spawn "bash" "/path/to/swaybg_helper.sh" "-c" "-d" "-f" "/path/to/wallpapers/folder"; }
```

Again, `-f` can be omitted as can `-d` if having a delay isn't a concern.

<br>

## mute_on_startup.sh

Super simple script that's just meant to auto-mute audio on startup. Helps avoid jump scares!

To use this, add a start-up line to your niri config file (e.g. `~/.config/niri/config.kdl`):

```kdl
spawn-at-startup "bash" "/path/to/mute_on_startup.sh"
```

This also resets the volume to 25%, though this can easily be changed if needed.
