#!/bin/bash

# Parse 'close left' flag if present
ENABLE_CLOSE_LEFT=false
if [[ $# -gt 0 ]]; then
	if [[ $1 == "-l" || $1 == "-left" || $1 == "--left" ]]; then
		ENABLE_CLOSE_LEFT=true
	else
		notify-send "close_helper.sh" "Flag error!\nProvide '-l' or '--left' to enable close-left mode"
	fi
fi

# Bail if we don't have a focused window
# -> Will also happen when overview is open, so try to close anyways
CURR_WIN_INFO=$(niri msg -j focused-window)
WINID_TO_CLOSE=$(jq .id <<< $CURR_WIN_INFO)
if [[ $WINID_TO_CLOSE == "null" ]]; then 
	niri msg action close-window
	exit
fi

# Close the window if floating or has no workspace
# -> No workspace can happen if window is being dragged, for example
WSPACE_ID=$(jq .workspace_id <<< $CURR_WIN_INFO)
IS_FLOATING=$(jq .is_floating <<< $CURR_WIN_INFO)
if $IS_FLOATING || [[ $WSPACE_ID == "null" ]]; then
	niri msg action close-window --id $WINID_TO_CLOSE
	exit
fi

# Close normally if we're in the first or second column (no point in forcing focus changes)
# -> Doing this for the second column is important for preserving 'always-center-single-column' behavior
COL_IDX=$(jq .layout.pos_in_scrolling_layout[0] <<< $CURR_WIN_INFO)
if [[ $COL_IDX -lt 3 ]]; then
	niri msg action close-window --id $WINID_TO_CLOSE
	exit
fi

# Get all window info in current workspace
ALL_WIN_INFO=$(niri msg -j windows | jq --argjson wsid $WSPACE_ID 'map(select(.workspace_id == $wsid))')

# If we're in a stacked column, just close normally (let niri handle focus change)
NUM_ROWS_IN_COL=$(jq --argjson cidx $COL_IDX 'map(select(.layout.pos_in_scrolling_layout[0] == $cidx)) | length' <<< $ALL_WIN_INFO)
if [[ $NUM_ROWS_IN_COL -gt 1 ]]; then
	niri msg action close-window --id $WINID_TO_CLOSE
	exit
fi

# Figure out which window (left or right) to focus after closing
LAST_COL_IDX=$(jq '[.[].layout.pos_in_scrolling_layout[0]] | max' <<< $ALL_WIN_INFO)
if $ENABLE_CLOSE_LEFT || [[ $COL_IDX -eq $LAST_COL_IDX ]]; then
	niri msg action focus-column-left
else
	niri msg action focus-column-right
fi
SIDE_WIN_ID=$(niri msg -j focused-window | jq .id)

# Close and force view re-alignment to get rid of empty space on the right
niri msg action close-window --id $WINID_TO_CLOSE
niri msg action focus-column-first
niri msg action focus-window --id $SIDE_WIN_ID

