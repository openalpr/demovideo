#!/usr/bin/python
# -*- coding: utf-8 -*-

# Given a SQLite database and a video, make a pimp demo video
from argparse import ArgumentParser
import os
import sys
from moviepy.editor import *
from frame_smoother import FrameSmoother
import cv2
import numpy
from alprstream import AlprStream
from openalpr import Alpr, VehicleClassifier
import hashlib
import json
import time
from data_formatter import get_vehicle_label

parser = ArgumentParser(description='OpenALPR Demo Movie Maker')

parser.add_argument("-v", dest="video", action="store", metavar='video', required=True,
                  help="Path to input video file" )

parser.add_argument("-c", "--country",  dest="country", action="store", default='us',
                  help="Country for plate recognition" )

parser.add_argument('output_video', metavar='output_video', type=str,
                   help='Path to output video')

parser.add_argument("--time_start", dest="time_start", action="store", metavar='video', type=float, default=0,
                  help="Time (in seconds) to start playback in the video" )

parser.add_argument('-p', '--preview', dest="preview", action='store_true', default=False,
                    help="Show a preview window rather than writing to file")

parser.add_argument('-g', '--gpu', dest="gpu", action='store_true', default=False,
                    help="Use GPU for processing")

parser.add_argument('--must_match_pattern', dest="must_match_pattern", action='store_true', default=False,
                    help="Only show plates that match the plate pattern")

parser.add_argument("--time_end", dest="time_end", action="store", metavar='time_end', type=float, default=0,
                  help="Time (in seconds) to end playback in the video" )

parser.add_argument("-f", "--font", dest="font", action="store", metavar='font', default='License-Plate-Regular',
                  help="Font to use for display.  e.g., License-Plate-Regular for US and FE-Regular for EU" )

parser.add_argument( "--font_size", dest="font_size", action="store", metavar='font_size', type=int, default=26,
                  help="Size of the font used to show the plate numbers" )

options = parser.parse_args()


if not os.path.isfile(options.video):
    print ("Cannot find input video file: " + options.video)
    sys.exit(1)



# First check if we have already processed this video.  If so, no sense in doing it again:

with open(options.video, 'rb') as inf:
    video_md5 = hashlib.md5(inf.read()).hexdigest()

cachefile = '/tmp/alprmakevideo_' + options.country + "_" + video_md5
print("Checking for cached video file for %s %s" % (options.video, cachefile))
if os.path.isfile(cachefile):
    # Load the pickle file
    print("Cache file exists, loading from disk")
    with open(cachefile, 'r') as inf:
        results_data = json.load(inf)
else:
    # Process the video frame by frame
    print("Cache file does not exist, processing video")

    alpr = Alpr(options.country, '', '')
    if not alpr.is_loaded():
        print('Error loading Alpr')
        sys.exit(1)

    alpr.set_detect_vehicles(True, True)

    alpr_stream = AlprStream(frame_queue_size=10, use_motion_detection=True)
    if not alpr_stream.is_loaded():
        print('Error loading AlprStream')
        sys.exit(1)

    vehicle = VehicleClassifier('', '')
    if not vehicle.is_loaded():
        print('Error loading VehicleClassifier')
        sys.exit(1)

    alpr_stream.connect_video_file(options.video, 0)
    frame_number = 0

    groups_array = []

    def process_group(popped_groups):
        global groups_array

        for group in popped_groups:
            unneeded_fields = ['vehicle_crop_jpeg', 'best_plate_jpeg']
            for field in unneeded_fields:
                del group[field]

            groups_array.append(group)
            print('=' * 40)
            print('Group from frames {}-{}'.format(group['frame_start'], group['frame_end']))
            if group['data_type'] == 'alpr_group':
                print('Plate: {} ({:.2f}%)'.format(group['best_plate']['plate'], group['best_plate']['confidence']))
            elif group['data_type'] == 'vehicle':
                print('Vehicle')

            print('Vehicle attributes')
            for attribute, candidates in group['vehicle'].items():
                print('\t{}: {} ({:.2f}%)'.format(attribute.capitalize(), candidates[0]['name'], candidates[0]['confidence']))
            print('=' * 40)

    while alpr_stream.video_file_active() or alpr_stream.get_queue_size() > 0 or len(alpr_stream.peek_active_groups()) > 0:
        frame_results = alpr_stream.process_batch(alpr)

        # Iterate each one so we make sure we print the processing note on every 100th frame
        for i in range(0, len(frame_results)):
            frame_number += 1
            if (frame_number % 100 == 0):
                active_groups = len(alpr_stream.peek_active_groups())
                queue_size = alpr_stream.get_queue_size()
                print("Processing frame {} -- Active groups: {:<3} \tQueue size: {}".format(frame_number, active_groups, queue_size))

        #print('Active groups: {:<3} \tQueue size: {}'.format(active_groups, alpr_stream.get_queue_size()))
        groups = alpr_stream.pop_completed_groups_and_recognize_vehicle(vehicle, alpr)
        process_group(groups)

    time.sleep(0.1)
    groups = alpr_stream.pop_completed_groups_and_recognize_vehicle(vehicle, alpr)
    process_group(groups)

    # Call when completely done to release memory
    alpr.unload()
    vehicle.unload()

    results_data = groups_array
    with open(cachefile, 'w') as outf:
        json.dump(results_data, outf)


video_clip = VideoFileClip(options.video)
w,h = moviesize = video_clip.size
fps = video_clip.fps
print ("FPS: " + str(video_clip.fps))

print ("Available fonts: ")
print (TextClip.list('font'))


def get_smoothed_data(group):

    plate_frames = []
    if 'plate_path' in group:
        path = group['plate_path']
    else:
        path = group['vehicle_path']

    for plate_path in path:
        plate_number = ''
        if 'best_plate_number' in group:
            plate_number = group['best_plate_number']
        print ("%s: frame_num: %d" % (plate_number, plate_path['f']))

        # Convert relative frame to actual
        plate_path['f'] = plate_path['f'] + group['frame_start']
        plate_path['center_x'] = int(plate_path['x'] + (plate_path['w'] / 2))
        plate_path['center_y'] = int(plate_path['y'] + (plate_path['h'] / 2))
        plate_frames.append(plate_path)
    smoothed_data = FrameSmoother(group, plate_frames)

    return smoothed_data


# Overlay the OpenALPR logo in the bottom right
if (w < 1000):
    logo_overlay = ImageClip('logo_words_small.png')
else:
    logo_overlay = ImageClip('logo_words.png')

logo_overlay = logo_overlay.set_opacity(0.6).set_pos((w-logo_overlay.w-10,h-logo_overlay.h-10))


#US Font
#font='License-Plate-Regular'
#EU Font
#font='FE-Regular'
#font_size=26
txt_fg_color = 'white'
text_bg_color = (0,0,0)
bg_opacity = 0.78

def get_x_y(fps, t, txt_width, txt_height, smoothed_data):
    offset_x = txt_width / -2
    offset_y = -1 * txt_height - 35
    x_y = smoothed_data.get_smoothed_xy_at(fps, t)
    x_y = (x_y[0] + offset_x, x_y[1] + offset_y)

    return x_y

def get_text_clip(group, smoothed_data, plate_number):

    time_start = smoothed_data.frame_to_time(fps, group['frame_start'])
    time_end = smoothed_data.frame_to_time(fps, group['frame_end'])

    txt = TextClip(plate_number, font=options.font,
                       color=txt_fg_color,fontsize=options.font_size )

    txt_col = txt.on_color(size=(txt.w,txt.h),
                      color=text_bg_color,  col_opacity=bg_opacity)

    print ("Time start: %f - Time end %f" % (time_start, time_end))



    txt_mov = txt_col.set_pos( lambda t: get_x_y( fps, t, txt.w, txt.h, smoothed_data) )#.set_start(time_start).set_end(time_end)

    return txt_mov


FREEZE_DURATION = 2

def get_insert_effect(group, time_start, smoothed_data):

    if (time_start < options.time_start):
        print ("Skipping effect with BLANK 2 second clip because %f < %f" % (time_start, options.time_start))
        #return ColorClip((w,h), col=(255,0,0), duration=FREEZE_DURATION)
        return None
    elif time_start > options.time_end and options.time_end != 0:
        print ("Skipping effect with NULL clip because %f > %f" % (time_start, options.time_end))
        return None

    # Add an effect the moment each plate is recognized
    freeze_frame = video_clip.to_ImageClip(time_start)

    painting = video_clip.fx( vfx.painting, saturation=1.9, black = 0.002).to_ImageClip(time_start)

    txt = TextClip(plate_number, font=options.font,
                       color=txt_fg_color,fontsize=options.font_size )

    txt_col = txt.on_color(size=(txt.w,txt.h),
                      color=text_bg_color,  col_opacity=bg_opacity)
    txt_mov = txt_col.set_pos( get_x_y( fps, time_start, txt.w, txt.h, smoothed_data) )

    painting_with_text = (CompositeVideoClip([painting])
                        .add_mask()
                        .set_duration(FREEZE_DURATION)
                        .crossfadein( 0.25)
                        .crossfadeout( 0.25))


    #audioclip = AudioClip(duration=0.88)

    painting_fade = CompositeVideoClip([freeze_frame, painting_with_text, txt_mov, logo_overlay]).set_duration(FREEZE_DURATION)


    return painting_fade

def get_audio_insert(group_count, time_start):

    if ((time_start < options.time_start or time_start > options.time_end) and options.time_end != 0):
        return None

    insert_offset = group_count * FREEZE_DURATION
    afc = AudioFileClip("sound_effect.wav", buffersize=100000, fps=44100)
    afc = afc.set_start(insert_offset + time_start)
    return afc



composites = []

inserts = []
audio_track = []

group_count = 0

for group in results_data:

    object_label = ''
    if group['data_type'] == 'alpr_group':

        object_label = group['best_plate_number']
        state = group['best_region']
        state_conf = group['best_region_confidence']
        if (state_conf > 80):
            object_label += " (%s)" % (state)

    elif group['data_type'] == 'vehicle':

        object_label = get_vehicle_label(group)

    print (" -- ")
    print (object_label)
    print (" --")

    # if len(plate_number) == 6:
    #     # Insert a space in the middle
    #     plate_number = plate_number[:3] + " " + plate_number[3:]


    smoothed_data = get_smoothed_data(group)

    # Add an effect the moment each plate is recognized
    time_start = smoothed_data.frame_to_time(fps, group['frame_start'])


    if (time_start < options.time_start):
        print ("Skipping effect because %f < %f" % (time_start, options.time_start))
        continue
    elif time_start > options.time_end and options.time_end != 0:
        print ("Skipping effect with NULL clip because %f > %f" % (time_start, options.time_end))
        continue

    # Get the text overlay
    txt_mov = get_text_clip(group, smoothed_data, object_label)
    composites.append(txt_mov)


    # add an insert effect at t + 2 frame
    effect_time = time_start + smoothed_data.frame_to_time(fps, 2)
    print ("Getting effect for %f" % (effect_time))
#    painting_fade = get_insert_effect(group, effect_time, smoothed_data)
    painting_fade = None
    if painting_fade is not None:
        inserts.append((effect_time, painting_fade))

    # sound_clippy = get_audio_insert(group_count, time_start)
    # if sound_clippy is not None:
    #     audio_track.append(sound_clippy)

    group_count += 1
    #
    # for plate in plates_for_group:
    #     center_point = plate['center']
    #     print plate['plate_number']
    #     print "Center: %d, %d" % (center_point[0], center_point[1])
    #     print "Size: %d, %d" % (plate['width'], plate['height'])


composites.insert(0, logo_overlay)
composites.insert(0, video_clip)

composited = CompositeVideoClip(composites)

all_clips = []
last_time_end = 0
for i in range(0, len(inserts)):
    if i  == len(inserts) - 1:
        end_clip_time = video_clip.end
    else:
        next_clip = inserts[i+1][0]
    all_clips.append(composited.subclip(last_time_end, inserts[i][0]))
    all_clips.append(inserts[i][1])
    last_time_end = inserts[i][0]

all_clips.append(composited.subclip(last_time_end, video_clip.end))


#final = final.subclip(0, video_clip.end)
final = concatenate_videoclips(all_clips)

#all_audio = CompositeAudioClip(audio_track).set_fps(44100).set_duration(final.duration)

if options.time_end == 0:
    options.time_end = final.duration
#final = final.set_audio(all_audio).subclip(options.time_start, options.time_end)
final = final.subclip(options.time_start, options.time_end)

if options.preview:
    final.preview()
else:
    final.write_videofile(options.output_video, fps=30, codec='libx264')
