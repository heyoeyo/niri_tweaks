#!/bin/bash

sleep 1.25 # Delay to make sure adjustment takes effect
wpctl set-volume @DEFAULT_AUDIO_SINK@ 25%
wpctl set-mute @DEFAULT_AUDIO_SINK@ 1

