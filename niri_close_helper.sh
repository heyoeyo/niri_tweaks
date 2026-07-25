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

# ----- Handle special cases -----

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

# If we're in the first column, close normally (nothing else to do)
COL_IDX=$(jq .layout.pos_in_scrolling_layout[0] <<< $CURR_WIN_INFO)
if [[ $COL_IDX -eq 1 ]]; then
	niri msg action close-window --id $WINID_TO_CLOSE
	exit
fi

# If we're in a stacked column, close normally (let niri handle focus change within column)
ALL_WIN_INFO=$(niri msg -j windows | jq --argjson wsid $WSPACE_ID 'map(select(.workspace_id == $wsid))')
NUM_ROWS_IN_COL=$(jq --argjson cidx $COL_IDX 'map(select(.layout.pos_in_scrolling_layout[0] == $cidx)) | length' <<< $ALL_WIN_INFO)
if [[ $NUM_ROWS_IN_COL -gt 1 ]]; then
	niri msg action close-window --id $WINID_TO_CLOSE
	exit
fi

# If there are exactly 2 (un-stacked) windows, close normally
# -> Odd detail, but needed to preserve 'always-center-single-column' behavior
NUM_WINS=$(jq length <<< $ALL_WIN_INFO)
if [[ $NUM_WINS -eq 2 ]]; then
	niri msg action close-window --id $WINID_TO_CLOSE
	exit
fi

# ----- End of special cases -----

# Figure out which window (left or right) to focus after closing
LAST_COL_IDX=$(jq '[.[].layout.pos_in_scrolling_layout[0]] | max' <<< $ALL_WIN_INFO)
if $ENABLE_CLOSE_LEFT || [[ $COL_IDX -eq $LAST_COL_IDX ]]; then
	niri msg action focus-column-left
else
	niri msg action focus-column-right
fi
AFTERCLOSE_WIN_ID=$(niri msg -j focused-window | jq .id)

# Close and force view re-alignment to get rid of empty space on the right
niri msg action close-window --id $WINID_TO_CLOSE
niri msg action focus-column-first
niri msg action focus-window --id $AFTERCLOSE_WIN_ID
