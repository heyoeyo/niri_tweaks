#!/bin/bash

# This script is used to automatically shift floating windows to the opposite
# side of the screen when changing focus on tiled windows
# Usage:
# 1) bash niri_focus_float_shifter.sh DIRECTION MIN_MOVE
# 2) bash niri_focus_float_shifter.sh DIRECTION LEFT_PAD RIGHT_PAD
#
# -> Option 1 will 'reflect' floating windows around the monitor center on focus change.
#    The provided number (MIN_MOVE) acts as a deadzone value, so
#    that windows close (according to MIN_MOVE) to the middle of the screen do not move
# -> Option 2 will just move windows to the far left/right edge of the screen with the given padding

# Read script flags
IS_FOCUS_LEFT=""
if [[ $1 == "l" || $1 == "left" ]]; then
	IS_FOCUS_LEFT=true
elif [[ $1 == "r" || $1 == "right" ]]; then
	IS_FOCUS_LEFT=false
fi

# Bail if direction is not set
if [[ -z $IS_FOCUS_LEFT ]]; then
	echo "Missing focus direction, must be one of: [left, l, right, r]"
	exit
fi
if $IS_FOCUS_LEFT; then FOCUS_DIR_CMD=focus-column-left; else FOCUS_DIR_CMD=focus-column-right; fi

# Read min-move arg, if present
MIN_MOVE=100
if [[ $2 -gt 0 ]]; then
	MIN_MOVE=$2
fi

# Check for left/right padding option
L_PAD=0
R_PAD=0
USE_PADDING=false
if [[ $3 -gt 0 ]]; then
	L_PAD=$2
	R_PAD=$3
	USE_PADDING=true
fi

# Get all info for windows on the current workspace
CURR_WSPACE_INFO=$(niri msg -j workspaces | jq '.[] | select(.is_focused)')
CURR_WSID=$(jq .id <<< $CURR_WSPACE_INFO)
WINS_ON_WSPACE=$(niri msg -j windows | jq --argjson wsid "$CURR_WSID" '[.[] | select(.workspace_id == $wsid)]')

# Do focus change
niri msg action $FOCUS_DIR_CMD

# Don't shift anything if we're already on a floating window
CURR_WIN=$(niri msg -j focused-window)
CURR_IS_FLOAT=$(jq .is_floating <<< $CURR_WIN)
if $CURR_IS_FLOAT; then
	exit 0
fi

# Shift floating windows by mirroring around screen center point
MONITOR_W=$(niri msg -j focused-output | jq .logical.width)
FLOAT_WIN_INFO=$(jq '[.[] | select(.is_floating)]' <<< $WINS_ON_WSPACE)
echo "$FLOAT_WIN_INFO" | jq -c '.[]' | while read -r ENTRY; do
	FID=$(jq .id <<< $ENTRY)
	WIN_W=$(jq .layout.window_size[0] <<< $ENTRY)
	
	# Switch between using explicit left/right positioning or mirroring
	if $USE_PADDING; then
		if $IS_FOCUS_LEFT; then
			NEW_X_POS=$((MONITOR_W - WIN_W - R_PAD))
		else
			NEW_X_POS=$L_PAD
		fi
	else
		# Mirror case: we 'flip' the current position left-to-right 
		CURR_X_POS=$(jq .layout.tile_pos_in_workspace_view[0] <<< $ENTRY)
		CURR_X_POS=${CURR_X_POS%.*} # Convert float to integer
		NEW_X_POS=$((MONITOR_W - WIN_W - CURR_X_POS))
		
		# Skip movement if window does not move (enough) in the correct direction
		if $IS_FOCUS_LEFT; then
			if [[ $(($NEW_X_POS - $CURR_X_POS)) -lt $MIN_MOVE ]]; then
				continue
			fi
		else
			if [[ $((CURR_X_POS - $NEW_X_POS)) -lt $MIN_MOVE ]]; then
				continue
			fi
		fi
	fi
    
    # Do actual float movement
    if [[ $NEW_X_POS -lt 0 ]]; then
    		# Negative values are interpreted as relative movements, so need to move to zero first then move relative 
    		# -> Should only happen in mirroring case (for windows partly offscreen)
		niri msg action move-floating-window --id $FID -x 0
		niri msg action move-floating-window --id $FID -x $NEW_X_POS
  	else
		niri msg action move-floating-window --id $FID -x $NEW_X_POS
	fi
done

