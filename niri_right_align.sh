#!/bin/bash

# Usage:
# bash niri_right_align.sh
# -> This script works by opening a 'dummy' window and quickly shifting
#    it around to alter the niri viewport alignment, then closing it.
#    By default, the script will search for common terminals on the system
#    to use as the 'dummy' window, but this can be provided directly to
#    the script, for example, to quickly open/close with alacritty use:
# bash niri_right_align.sh alacritty

# Use provided script arg as open command, if present
DUMMY_OPEN_CMD=null
if [ $1 ]; then
	# Bail if user gives a bad command
	if ! $(command -v $1 >/dev/null 2>&1); then
		notify-send "$(basename $BASH_SOURCE)" "Invalid command: $1"
		exit 1
	fi
	DUMMY_OPEN_CMD=$1
	
else
	# Look for common terminals to use as dummy window
	for name in alacritty foot kitty konsole xfce4-terminal ptyxis; do
		if command -v $name >/dev/null 2>&1; then
			DUMMY_OPEN_CMD=$name
			break
		fi
	done
	
	# Bail if we don't have a valid dummy
	if [[ $DUMMY_OPEN_CMD == null ]]; then
		notify-send "$(basename $BASH_SOURCE)" "Couldnt find an application to open for right-align!\nPlease provide an application name to the script"
		exit 1
	fi
fi

# Force window to be left-most column
ORIG_INFO=$(niri msg -j focused-window)
if [[ $ORIG_INFO == null ]]; then exit; fi
ORIG_COL_IDX=$(jq .layout.pos_in_scrolling_layout[0] <<< $ORIG_INFO)
if [[ $ORIG_COL_IDX -ne 1 ]]; then
	niri msg action focus-column-first
fi

# Launch dummy program
FIRST_COL_WIN_ID=$(niri msg -j focused-window | jq .id)
$DUMMY_OPEN_CMD &

# Wait for dummy to open (or stop if we don't get an open event soon enough)
EVT_COUNT=0
while read -r event; do
	EVT_COUNT=$((EVT_COUNT+1))
	event_name=$(jq -r 'keys[0]' <<< $event)
	case "$event_name" in "WindowOpenedOrChanged") break;; esac
	if [[ EVT_COUNT -gt 12 ]]; then exit 1; fi
done < <(niri msg -j event-stream)

# Re-focus original window if focus hasn't changed
DUMMY_INFO=$(niri msg -j focused-window)
DUMMY_ID=$(jq .id <<< $DUMMY_INFO)
if [[ $DUMMY_ID -eq $FIRST_COL_WIN_ID ]]; then
	ORIG_ID=$(jq .id <<< $ORIG_INFO)
	niri msg action focus-window --id $ORIG_ID
	exit 1
fi

# Unstack dummy if need (e.g due to tilemod)
DUMMY_ROW_IDX=$(jq .layout.pos_in_scrolling_layout[1] <<< $DUMMY_INFO)
if [[ $DUMMY_ROW_IDX -gt 1 ]]; then
	niri msg action consume-or-expel-window-left --id $DUMMY_ID
	niri msg action set-column-width 50% # Fixes bug if window if maximized
	sleep 0.1
fi

# Figure out workspace index to move dummy into
ORIG_WSID=$(jq .workspace_id <<< $ORIG_INFO)
ORIG_WSIDX=$(niri msg -j workspaces | jq --argjson wsid $ORIG_WSID '.[] | select(.id==$wsid)' | jq .idx)
NEXT_WSIDX=$((ORIG_WSIDX + 1))

# Trick niri into right view alignment
niri msg action move-column-left
niri msg action set-column-width 80% # Needed to 'push' narrow windows to the right!
niri msg action focus-column-right
niri msg action move-window-to-workspace $NEXT_WSIDX --window-id $DUMMY_ID --focus false
niri msg action close-window --id $DUMMY_ID

# Re-focus original window if needed
# -> This is needed to right-align windows that are between other windows
if [[ $ORIG_COL_IDX -gt 1 ]]; then
	ORIG_ID=$(jq .id <<< $ORIG_INFO)
	niri msg action focus-window --id $ORIG_ID
fi
