OpenALPR Demo Video Maker
------------------------------

This utility creates video files like the following:

[![OpenALPR Demo Video](https://img.youtube.com/vi/I6gIB7pfzwg/0.jpg)](https://www.youtube.com/watch?v=I6gIB7pfzwg)

The utility takes the following inputs:

  - SQLite file generated from OpenALPR Forensic Plate Finder 
  - MP4 Video file containing the plates which were detected with the Forensic Plate Finder

The output is a video file with the plate numbers overlayed


Installation
-----------------

  sudo apt-get update && apt-get install python-virtualenv
  virtualenv venv
  source venv/bin/activate
  pip install -r requirements.txt


Usage
---------

- Run the OpenALPR Forensic Plate Finder on your video to produce a SQLite file containing the plates
- python make_video.py -s [path to sqlite] -v [path to video] [output_video_filename]
