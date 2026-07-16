# niri tweaks

This repo holds some basic scripts that provide additional functionality for the [niri](https://github.com/YaLTeR/niri) wayland compositor. The scripts are all independent of one another, so any one can be used without needing the others.

#### Scripts:
- [niri_tilemod.py](#niri_tilemodpy)
- [niri_custom_layout.py](#niri_custom_layoutpy)
- [niri_spawnjump.py](#niri_spawnjumppy)
- [niri_maximize_helper.py](#niri_maximize_helperpy)
- [niri_workspace_helper.py](#niri_workspace_helperpy)
- [niri_float_helper.py](#niri_float_helperpy)
- [niri_close_helper.sh](#niri_close_helpersh)
- [niri_peekaboo.py](#niri_peekaboopy)
- [niri_overview_bind.py](#niri_overview_bindpy)
- [niri_parse_keybinds.py](#niri_parse_keybindspy)
- [niri_search_window.py](#niri_search_windowpy)
- [niri_unstack_all.py](#niri_unstack_allpy)
- [niri_doubletap.py](#niri_doubletappy)
- [niri_window_details.sh](#niri_window_detailssh)
- [fuzzel_helper.sh](#fuzzel_helpersh)
- [swaybg_helper.sh](#swaybg_helpersh)
- [mute_on_startup.sh](#mute_on_startupsh)
- [niri_tile_to_n.py](#niri_tile_to_npy)

Scripts that start with `niri` make use of the [niri IPC](https://github.com/niri-wm/niri/wiki/IPC) in some way.

All scripts are compatible with the newest release of niri ([v26.04](https://github.com/niri-wm/niri/releases)) and generally compatible with older versions as well. Usage of each script is explained below.


## niri_tilemod.py

<p align="center">
  <img src="https://github.com/user-attachments/assets/1fc67144-5eaf-4145-8668-ccb84471df8c" width=400 height=167>
</p>

This script auto-stacks windows within a specified range of columns. The stacking behavior can be configured on a per-workspace or monitor basis. It also supports 'maximize solo windows' and 'right-to-left' behaviors. It uses the niri [event stream](https://github.com/niri-wm/niri/wiki/IPC#event-stream) and requires niri version 25.08 or greater.

### Quick test run

If you'd like to quickly try this out, use the following terminal command:
```bash
curl https://raw.githubusercontent.com/heyoeyo/niri_tweaks/refs/heads/main/niri_tilemod.py | python3
```
This downloads the script text and pipes it straight into python to run it. After doing this, try opening 3 or more windows to see the effect. Hitting ctrl+c or closing the terminal will disable the effect.

### Permanent use

To have the script always running, either [clone](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) this repo, or otherwise copy the contents of [the script](https://github.com/heyoeyo/niri_tweaks/blob/main/niri_tilemod.py) into a file somewhere on your machine. Then you just need to update your [niri config file](https://github.com/YaLTeR/niri/wiki/Configuration:-Introduction) (usually in `~/.config/niri/config.kdl`) to run the script on start-up:
```kdl
spawn-sh-at-startup "python3 /path/to/niri_tilemod.py"
```

You'll have to log-out/log-in for this to take effect.

> [!Tip]
> Replacing the default [left & right movement](https://github.com/niri-wm/niri/blob/0777769e719b7c9b7c980d4ea66288bfbb4da5b3/resources/default-config.kdl#L413-L420) keybinds with `consume-or-expel-window-left` & `consume-or-expel-window-right` makes auto-stacking _far more practical_ within niri.

### Configuration

There are many configuration options, which can be seen by running the script in a terminal with the `--help` flag:

```bash
python3 /path/to/niri_tilemod.py --help
```

Settings can be configured across different workspaces/monitors. This is done using a `tilemod_config.toml` file which (by default) is expected to be located in the niri config folder. Here's an example config:

<details>

<summary>~/.config/tilemod_config.toml</summary>

```toml
[default]
num_stack = 2
column_bounds = [2, 2] # niri indexing starts at 1
maximize_solos_on_open = true
maximize_solos_on_close = true
collapse_solos_on_open = true
allow_outer_stack = true
apply_to_moved_windows = false
autostack_last_column_only = false
right_to_left = false
action_maximize = "MaximizeColumn" # or "MaximizeWindowToEdges" or "FullscreenWindow"
disabled = false

# Always stack 2x2x2x2... on workspace index 2
[workspaces.idx.2]
column_bounds = [0, 100]
num_stack = 2

# Open right-to-left on workspace ID 3, with no stacking
[workspaces.id.3]
right_to_left = true
num_stack = 0

# Disable tilemod on monitor named 'HDMI-A-7'
[outputs.name.HDMI-A-7]
disabled=true
```
</details>

Configuration tries to match by workspaces first, then outputs (e.g. monitors) and finally by the default settings if no other match is found. When setting up more elaborate configurations, the script can be run with the `-k` flag to print out the active config in a terminal (based on where the terminal is located). If the script is already running, changes to the config can be made to take effect by toggling the niri overview.

> [!Note]
> Support for .toml files requires python v3.11+. If using an earlier version of python, a .json file can be used instead. It's recommended to use a [toml-to-json](https://transform.tools/toml-to-json) converter to create this.

<br>

## niri_custom_layout.py

This script allows for quickly forcing windows into a custom layout using a keypress. You can add a line to the niri config to trigger it with a keypress, like:

```kdl
Mod+A { spawn-sh "python3 /path/to/niri_custom_layout.py 2 3"; }
```

The integer values added to the end of this command (e.g. `2 3`) determines the layout. The number of integers sets the number of columns and each integer controls how many rows to use per column. For example adding `1 3 2` would produce a layout with 3 columns, the first having 1 row, the next having 3, and the last having 2. There are a number of customization flags that can be found by running the script in a terminal:

```bash
python3 niri_custom_layout.py --help
```

Some of the flags allow for customizing both the window width and heights. For example, adding the `-w` flag will auto-scale the column widths to fit on screen, regardless of the number of columns. It's also possible to set a different width per-column by including numbers after `-w`, like `-w 50 0 25` (where `0` means to use the existing window width). Window heights can similarly be set using `-r` to get more elaborate layouts, like with the following command:

```kdl
Mod+A { spawn-sh "python3 /path/to/niri_custom_layout.py 3 2 3 -w 25 50 25 -r 25 25 50 80 20 0 0 0 -a l -uw 50"; }
```

This would produce the following layout (assuming 8 windows are available!):
```
┌───┐┌────────────┐┌───┐
└───┘│            ││   │
┌───┐│            │└───┘
└───┘│            │┌───┐
┌───┐│            ││   │
│   ││            │└───┘
│   │└────────────┘┌───┐
│   │┌────────────┐│   │
└───┘└────────────┘└───┘
```


By default, triggering the script when windows are already in the correct layout will 'unstack' them, though this can be disabled (see the `--disable_unstack` flag). Note that the [maximize helper](#niri_maximize_helperpy) script can be used to toggle window maximization without breaking the layout.


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
Mod+T { spawn-sh "python3 /path/to/niri_spawnjump.py alacritty -w -p -s"; }
```

For flatpaks, use the entire run command (inside of quotes to indicate it's one command):

```kdl
Mod+B { spawn-sh "python3 /path/to/niri_spawnjump.py 'flatpak run app.zen_browser.app'"; }
```
By default, this will search for existing instances based on the `app-id` that niri assigns, assuming this matches the name used to run the application (e.g. `alacritty` or `app.zen_browser.app`). Some applications seem to use a different name, like the flatpak for Chromium, which has an `app-id` of `chromium-browser`. For these applications, the `app-id` can be passed as a second argument:

```kdl
Mod+B { spawn-sh "python3 /path/to/niri_spawnjump.py 'flatpak run org.chromium.Chromium' 'chromium-browser'"; }
```

To help figure out the `app-id` for these sorts of applications, run this script without any arguments. The `app-id` of the currently focused window will then be printed out in the terminal.

### Scratchpad

The script includes support for providing a 'scratchpad' workspace name (use `-t workspacename`), this will auto-enable `--push` and `--pull` and will push windows to the provided workspace name, instead of pushing them to the end of the current workspace:

```kdl
Mod+T { spawn-sh "python3 /path/to/niri_spawnjump.py alacritty -t scratch"; }
```

Your niri config needs to include a line like: `workspace "scratch"` for this command to work properly.

<br>

## niri_maximize_helper.py

<p align="center">
  <img src="https://github.com/user-attachments/assets/ce948365-ff9d-4fd0-9ce5-9ec7b801d9fc" width=540 height=226>
</p>

This script acts like a `maximize-window` command (as opposed to the built-in `maximize-column` version). It will automatically unstack windows prior to maximizing and keeps track of the window positioning so that it can be restored when toggling the maximization state. It can be set up as a keybind using:

```kdl
Mod+M { spawn-sh "python3 /path/to/niri_maximize_helper.py"; }
```

The script can alternatively be made to run the other maximization commands (e.g. `maximize-window-to-edges` or `fullscreen-window`) by adding the command to the end of the script call:

```kdl
Mod+M { spawn-sh "python3 /path/to/niri_maximize_helper.py fullscreen-window"; }
```

This leads to support for restoring stacked window positions when toggling out of a fullscreen state for example. More options can be seen by running the script in a terminal with the `--help` flag.

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

## niri_float_helper.py

<p align="center">
  <img src="https://github.com/user-attachments/assets/edfcbc95-dbc1-48ed-9c6f-38bdf776b9c2" width=540 height=225>
</p>

The original idea for this script comes from a [post](https://github.com/niri-wm/niri/discussions/4273) on the niri discussion board. It uses [slurp](https://github.com/emersion/slurp) to decide where floating windows should be placed. It also remembers the width of windows before floating, so they can be restored when reverting to tiling.

The script is meant to be triggered with a keybind in the niri config:

```kdl
Mod+X { spawn-sh "python3 /path/to/niri_float_helper.py"; }
```

By default, this will display 5 placement regions. Clicking on a region will 'float' the current focused window into position. Pressing the key twice (without interacting with the regions) will 'un-float' the focused window if already floating.

The regions can be customized by providing strings in `x y w h` order to the script. Negative x/y values can be used to move relative to the right/bottom edges, and percentages can be given as well. For example:

```kdl
Mod+X { spawn-sh "python3 /path/to/niri_float_helper.py '10 20 48.5% 75%' '-10 -20 48.5% 50%'"; }
```

This provides two regions, one large region in the top-left and another smaller region in the bottom right. Alternatively, the script can be run with the `-d` flag, which enables directly drawing the float region for the focused window. For example:

```kdl
Mod+MouseMiddle repeat=false { spawn-sh "python3 /path/to/niri_float_helper.py -d"; }
```

Note that the drawn region can be moved around by holding space (a feature of `slurp`)!

There are several other script options, including settings to adjust the overlay coloring, which can be seen by running the script in a terminal with the `--help` flag:

```bash
python3 /path/to/niri_float_helper.py --help
```

For example, one helpful flag is `-r` which can be used to print drawn region sizing into a terminal. This can help in setting up custom regions.

#### Note on X/Y Offsets

Niri window movement uses a co-ordinate system that's offset from the full display (and `slurp`), which can lead to errors in window positioning. These offsets are determined on first run and recorded in a temporary file, but this can lead to some jittering. To prevent this from happening, provide the offsets to the script using the `-xo` and `-yo` flags. A notification is given to report the value of the offsets on first run, if missed, they'll be available in a temporary file: `/tmp/niri_float_helper/xyoffsets.info`

<br>

## niri_close_helper.sh

This script helps to avoid having an empty space after closing windows under certain conditions (see issue [#2815](https://github.com/niri-wm/niri/discussions/2815)). It's meant to replace the original `close-window` command as follows:

```
Mod+Q { spawn-sh "bash /path/to/niri_close_helper.sh"; }
```

Optionally, a `--left` (or `-l`) flag can be added to the end of this command to enable a 'close & focus left' behavior when closing eliminates a column.




<br>

## niri_peekaboo.py

<p align="center">
  <img src="https://github.com/user-attachments/assets/f3824bd1-b240-4146-a8f2-6de68c4a5aa9" width=550>
</p>

This is an experimental script used to pull nearby windows into view as floats for quick interactions, without needing to scroll the view. This is meant for use on maximized or fullscreen windows. Non-full-width windows won't work as expected and may require some IPC updates before they can be properly supported.

The script can be bound to a keypress in your niri config:
```kdl
Mod+P { spawn-sh "python3 /path/to/niri_peekaboo.py"; }
```

Running this command once will float window(s) in the column to the right of where you're focused and move the window(s) into view on the left. Running it again will return the floating windows back to the column on the right (e.g. offscreen).

There are several configuration options which can be viewed by running (in a terminal):
```bash
python3 /path/to/niri_peekaboo.py --help
```


<br>

## niri_overview_bind.py

This is a [simple script](https://github.com/heyoeyo/niri_tweaks/blob/main/niri_overview_bind.sh) inspired by a post on the niri issue board ([#2842](https://github.com/YaLTeR/niri/discussions/2842)) about setting up different keybinds in overview mode. The general script usage is:

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
  <img src="https://github.com/user-attachments/assets/45f4eecd-ae60-46f3-923a-a2d7b36800b6" width=600>
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

This script acts as a text-based alternative to the built-in 'alt-tab' functionality. When called it uses [fuzzel](https://codeberg.org/dnkl/fuzzel) to fuzzy search all Niri windows. Once a window is selected Niri will switch to it.

```kdl
Alt+Tab { spawn-sh "python3 /path/to/niri_search_window.py"; }
```

Note that the built-in (graphical) alt-tab functionality is available on both `Alt+Tab` and `Mod+Tab`, so it's possible to replace one shortcut with this script while keeping the built-in option on the other.

<br>

## niri_unstack_all.py

Basic helper script used to unstack all columns on a workspace. It can also be used to cycle [preset widths](https://github.com/niri-wm/niri/blob/6f1a2c5f0e8274223d4204b1f8d6f7f91538967e/resources/default-config.kdl#L125) on all windows. Bind to a keypress using:

```kdl
Mod+Z { spawn-sh "python3 /path/to/niri_unstack_all.py"; }
```

Include the `-c` flag to cycle all column widths or `-c 25` to set all columns to a 25% width (or any other proportion). The `-r` flag can be added to reset all window heights.

<br>

## niri_doubletap.py

Mostly for fun, this script is meant to provide the ability to only run niri commands on double-tap. It can (optionally) also run a different command on single tap. The simplest usage is to run the script followed by the command to run on double-tap:

```kdl
Mod+M repeat=false { spawn-sh "python3 /path/to/niri_doubletap.py maximize-window-to-edges"; }
```

For example, this command will only toggle `maximize-window-to-edges` when double-tapping `M`. There are several script flags, which can be seen by running the script in a terminal with the `--help` flag. One option, the `-s` flag, allows for setting single-tap commands:

```kdl
Mod+M repeat=false { spawn-sh "python3 /path/to/niri_doubletap.py maximize-window-to-edges -s maximize-column"; }
```

This will maximize a column when pressing `M` once, but toggle `maximize-window-to-edges` when double tapping. This helps avoid having separate keybinds for related functionality.

#### Other uses

One obvious usage is to bind something like `focus-column-left` to single-tap and `focus-monitor-left` to double tap. However, doing so will always trigger a column-focus change before changing the monitor focus, which may be undesirable. To help with this, a 'reversal' command (e.g. `focus-column-right`) can be given using `-r`, so for example:

```kdl
Mod+Left repeat=false { spawn-sh "python3 /path/to/niri_doubletap.py focus-monitor-left -s focus-column-left -r focus-column-right"; }
```

This will result in `focus-monitor-left` always being preceeded by a `focus-column-right`, to help counter the unavoidable `focus-column-left` call needed to trigger the double-tap.

Another way to use this script is to remove `repeat=false` from the keybind and then set a _lower-bound_ timing window for registering double-taps. This can make the script trigger commands only when a key is held down. This is a somewhat hacky thing to do and requires carefully picking the double tap (`-dt`) and lower-bound (`-lb`) timings. For example, on my machine `-dt 700 -lb 60` seems to work.

<br>

## niri_window_details.sh

This script is mostly used for debugging and is an alternative to running `niri msg pick-window` in a terminal. It prints out basic window information from calling `niri msg focused-window` into a notification. For example, this can print out the `app-id` of a window, making it useful for setting up window rules.

A keybinding can be added to the niri config file to trigger this:
```kdl
Mod+Backslash { spawn-sh "bash /path/to/niri_window_details.sh"; }
```

Pressing this keybinding while focusing a window will give you a notification that includes basic information about that window. It's also easy to [modify the script](https://github.com/heyoeyo/niri_tweaks/blob/main/niri_window_details.sh) to print out other info if needed.

<br>

## fuzzel_helper.sh

The normal behavior of the niri application launcher ([fuzzel](https://codeberg.org/dnkl/fuzzel)) is to only open when launched. This script makes it toggle on/off, so that a single command can be used to both open and close (i.e. cancel), which seems more intuitive.

### Usage

You need to add (or most likely [replace](https://github.com/YaLTeR/niri/blob/e837e39623457dc5ad29c34a5ce4d4616e5fbf1e/resources/default-config.kdl#L366)) a keybinding in the niri config file to run this script, for example:
```kdl
Mod+0 repeat=false { spawn-sh "bash /path/to/fuzzel_helper.sh"; }
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
spawn-sh-at-startup "bash /path/to/swaybg_helper.sh -f /path/to/wallpapers/folder"
```

The `-f` flag can be ommited if images are placed in `~/Pictures/Wallpapers`. Adding the `-c` flag will result in the wallpaper changing on each login.

#### Cycle wallpaper on keypress

To cycle backgrounds on a keypress, add the following keybind:
```kdl
Mod+Shift+W { spawn-sh "bash /path/to/swaybg_helper.sh -c -d -f /path/to/wallpapers/folder"; }
```

Again, `-f` can be omitted as can `-d` if having a delay isn't a concern.

<br>

## mute_on_startup.sh

Super simple script that's just meant to auto-mute audio on startup. Helps avoid jump scares!

To use this, add a start-up line to your niri config file (e.g. `~/.config/niri/config.kdl`):

```kdl
spawn-sh-at-startup "bash /path/to/mute_on_startup.sh 10"
```

The `10` in this example sets the initial volume percentage after un-muting. If not set, the script defaults to 25%.

<br>

## niri_tile_to_n.py
(_legacy_)

Please use [tilemod](#niri_tilemodpy) instead. For the original documentation for this script, please see an older commit ([a1b8a16](https://github.com/heyoeyo/niri_tweaks/tree/a1b8a16c7b39b5b0d6147682314a10b7264fa9f0#niri_tile_to_npy)).
