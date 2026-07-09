#!/bin/bash

# Set initial volume (i.e. value to use on un-muting)
INIT_VOLUME=$1
if [ -z $INIT_VOLUME ]; then
	INIT_VOLUME=25
fi

sleep 1.25 # Delay to make sure adjustment takes effect
wpctl set-volume @DEFAULT_AUDIO_SINK@ "$INIT_VOLUME%"
wpctl set-mute @DEFAULT_AUDIO_SINK@ 1

