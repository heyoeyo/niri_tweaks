# niri tweaks

This repo holds some basic helper scripts (currently only 1) that are used to modify the behavior of the [niri](https://github.com/YaLTeR/niri) wayland compositor.

### niri_tile_to_n.py

This script makes niri behave more like a 'regular' tiling window manager up to the point of having 'N' windows (where N is adjustable, 3 by default), after which windows will be added in the normal scrolling pattern. It uses the [niri IPC](https://github.com/YaLTeR/niri/wiki/IPC) and is only tested on niri version 25.08 so far.

#### Example

The example below shows the sequence of opening 4 windows, when 'N=3'. The first opened window (A) will be maximized:
```
┌───────────────┐         
│               │         
│       A       │         
│               │         
│               │         
└───────────────┘         
```

Opening a second window (B) will collapse (A) so the windows tile:
```
┌──────┐ ┌──────┐
│      │ │      │
│  A   │ │  B   │
│      │ │      │
│      │ │      │
└──────┘ └──────┘
```

Opening a third window (C) will begin stacking windows on the right:
```             
┌──────┐ ┌──────┐
│      │ │  B   │
│  A   │ └──────┘
│      │ ┌──────┐
│      │ │  C   │
└──────┘ └──────┘
```

The fourth window (D), opens off-screen in the normal niri scrolling pattern:
```                
┌──────┐ ┌──────┐ ┌──────┐
│      │ │  B   │ │      │
│ A    │ └──────┘ │ D    │
│      │ ┌──────┐ │      │
│      │ │  C   │ │      │
└──────┘ └──────┘ └──────┘
```

Any other windows opened will continue to be added to the right.


#### Quick test run

This script uses python and doesn't require any build step or dependencies (just need a new-ish version of python3, 3.7+ should be ok). If you'd like to quickly try this out, use the following terminal command:
```bash
curl https://raw.githubusercontent.com/heyoeyo/niri_tweaks/refs/heads/main/niri_tile_to_n.py | python3
```
This downloads the script text and pipes it straight into python to run it. After doing this, try opening 3 or more windows to see the effect. Hitting ctrl+c or closing the terminal will disable the effect.

#### Permanent use

To have the script always running, either clone this repo, or otherwise copy the contents of [the script](https://github.com/heyoeyo/niri_tweaks/blob/main/niri_tile_to_n.py) into a file somewhere on your machine. Then you just need to update your [niri config file](https://github.com/YaLTeR/niri/wiki/Configuration:-Introduction) (usually in `~/.config/niri/config.kdl`) to run the script on start-up:
```bash
spawn-at-startup "python3" "/path/to/niri_tile_to_n.py"
```

You'll have to log-out/log-in for this to take effect.

#### Customization

There are a few flags for toggling features (like `-x` for disabling auto-maximization of new windows) which can be found by running:
```bash
python3 niri_tile_to_n.py --help
```

The script itself is one big (ugly) python file, but should be easy to edit if you want more specific customizations. Most of the script is dedicated to listening to the niri IPC, while the [last 50 lines](https://github.com/heyoeyo/niri_tweaks/blob/d4f64bf4d79407f3cb70283392aadfb96aa240ff/niri_tile_to_n.py#L522-L568) or so hold all of the custom windowing logic (so hack away here if you want some more custom behavior).