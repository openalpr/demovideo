#!/bin/bash

python make_video.py -s eunightvlad/night_vlad.sqlite  -v $alpr/samples/testing/videos/night_vlad.mp4 --time_start 60 --time_end 600  --font_size 30 -f FE-Regular eunight.mp4
