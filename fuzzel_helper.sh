#!/bin/bash

# Helper script, used to toggle fuzzel on and off from a single command
# e.g. the same key which opens fuzzel will close it

# Usage:
# Add the following line to the niri config to open/close fuzzel on super+0:
#   Mod+0 repeat=false { spawn "bash" "/path/to/this_script.sh"; }
# This can be combined with keyd to have the launcher work with
# a single key press (e.g. just the super key), see niri issue #605:
# https://github.com/YaLTeR/niri/issues/605#issuecomment-2600315134

# Open fuzzel or close it if it's already open
PREV_FUZZEL_PID=$(pidof fuzzel)
if [[ -z "$PREV_FUZZEL_PID" ]]; then
  fuzzel
else
  kill "$PREV_FUZZEL_PID"
fi

