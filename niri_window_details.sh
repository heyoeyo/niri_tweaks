#!/bin/bash

NIRIJSON=$(niri msg --json focused-window)
TITLE=$(jq -r .title <<<"$NIRIJSON")
APPID=$(jq -r .app_id <<<"$NIRIJSON")
WINID=$(jq -r .id <<<"$NIRIJSON")
PID=$(jq -r .pid <<<"$NIRIJSON")

notify-send "$TITLE" "appid: $APPID\n(winid: $WINID  pid: $PID)"

