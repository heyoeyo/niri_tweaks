#!/bin/bash

# Script used to set or cycle background images using swaybg
# Can be called with flags:
#   -c or --cycle
#   -n or --notify
#   -d or --delay
# If no flag is provided, the last-used wallpaper will be set as the background

# Usage:
# To use in niri on startup (to set the initial background):
#   spawn-at-startup "bash" "/path/to/this_script.sh"
# To bind to a key for cycling the wallpaper with a delay:
#   Mod+Shift+W { spawn "bash" "/path/to/this_script.sh" "--cycle" "-d"; }

# Path to folder containing wallpapers (must end in * to work properly!)
# (expecting only images, there's no checking for invalid files)
BG_FOLDER_PATH="$HOME/Pictures/Wallpapers/*"

# Read script flags
FLAG_CYCLE=false
FLAG_NOTIFY=false
FLAG_DELAY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--cycle) FLAG_CYCLE=true ;;
    -n|--notify) FLAG_NOTIFY=true ;;
    -d|--delay) FLAG_DELAY=true ;;
    *) echo "Unknown option: $1" ;;
  esac
  shift
done

# Choose most-recent accessed file by default or least-recent to cycle
PICK_CMD="head -n 1"
if $FLAG_CYCLE; then
  PICK_CMD="tail -n 1"
fi
BG_SELECT_PATH=$(ls -tu $BG_FOLDER_PATH | $PICK_CMD)

# Notify if needed
if $FLAG_NOTIFY; then
  notify-send "Wallpaper Changed" $(basename "$BG_SELECT_PATH")
fi

# Get previous swaybg so we can stop it once we start a new instance
PREV_SWAYBG_PID=$(pidof swaybg)

# Update access on selected file, for cycling
touch -ac $BG_SELECT_PATH
swaybg -i "$BG_SELECT_PATH" &

# Wait a bit and then stop prior swaybg instances (if present)
# -> Delay because it can take a moment for new bg to load
# -> If user spams this script, we can end up creating many instances of sway because of this delay!
#    The kill command will clean them all up, but it's a bit messy
if $FLAG_DELAY; then
  sleep 0.5
fi

# Close all prior swaybg instances (would be 'behind' current wallpaper)
if [[ -n "$PREV_SWAYBG_PID" ]]; then
  kill $PREV_SWAYBG_PID
fi
