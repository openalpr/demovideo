#!/usr/bin/python
# -*- coding: utf-8 -*-

# Given a SQLite database and a video, make a pimp demo video
from argparse import ArgumentParser
import os
import sys
from moviepy.editor import *
import sqlite3
from frame_smoother import FrameSmoother
import cv2
import numpy

parser = ArgumentParser(description='Vehicle color detector')

parser.add_argument("-s", dest="sqlite", action="store", metavar='sqlite', required=True,
                  help="Path to SQLite input file" )

parser.add_argument("-v", dest="video", action="store", metavar='video', required=True,
                  help="Path to input video file" )

parser.add_argument('output_video', metavar='output_video', type=str,
                   help='Path to output video')

parser.add_argument("--time_start", dest="time_start", action="store", metavar='video', type=float, default=0,
                  help="Time (in seconds) to start playback in the video" )

parser.add_argument('-p', '--preview', dest="preview", action='store_true', default=False,
                    help="Show a preview window rather than writing to file")

parser.add_argument("--time_end", dest="time_end", action="store", metavar='time_end', type=float, default=0,
                  help="Time (in seconds) to end playback in the video" )

parser.add_argument("-f", "--font", dest="font", action="store", metavar='font', default='License-Plate-Regular',
                  help="Font to use for display.  e.g., License-Plate-Regular for US and FE-Regular for EU" )

parser.add_argument( "--font_size", dest="font_size", action="store", metavar='font_size', type=int, default=26,
                  help="Size of the font used to show the plate numbers" )

options = parser.parse_args()

if not os.path.isfile(options.sqlite):
    print ("Cannot find sqlite file: " + options.sqlite)
    sys.exit(1)

if not os.path.isfile(options.video):
    print ("Cannot find input video file: " + options.video)
    sys.exit(1)

def get_center_point(plate):
    x1 = int(plate['x1'])
    y1 = int(plate['y1'])
    x2 = int(plate['x2'])
    y2 = int(plate['y2'])
    x3 = int(plate['x3'])
    y3 = int(plate['y3'])
    x4 = int(plate['x4'])
    y4 = int(plate['y4'])

    points = [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
    moment = cv2.moments(numpy.array(points))
    center_point_x = int(round(moment['m10']/moment['m00']))
    center_point_y = int(round(moment['m01']/moment['m00']))

    # center_point_x = x1 + ((x2 - x1) / 2)
    # center_point_y = y3 + ((y3 - y2) / 2)

    print ("%s: x1/y1 Points: %d, %d -- Center: %d, %d" % (plate['plate_number'], x1, y1, center_point_x, center_point_y))
    return (center_point_x, center_point_y)

def get_width_height(plate):
    x1 = int(plate['x1'])
    y1 = int(plate['y1'])
    x2 = int(plate['x2'])
    y2 = int(plate['y2'])
    x3 = int(plate['x3'])
    y3 = int(plate['y3'])
    x4 = int(plate['x4'])
    y4 = int(plate['y4'])

    width = (x2 - x1)
    height = (y3 - y2)
    return (width, height)


def get_plates_for_group(id):

    colums_i_want = ['id', 'country', 'plate_number', 'confidence', 'frame_num', 'x1', 'x2', 'x3', 'x4',
                     'y1', 'y2', 'y3', 'y4', 'region']

    all_results = []
    sql_statement = "SELECT " + ','.join(colums_i_want) + " FROM plate WHERE group_id=%d ORDER BY frame_num ASC" % (id)

    for row in c.execute(sql_statement):
        result_obj = {}
        index = 0
        for column in colums_i_want:
            result_obj[column] = row[index]
            index += 1

        result_obj['center_x'] = get_center_point(result_obj)[0]
        result_obj['center_y'] = get_center_point(result_obj)[1]
        result_obj['width'] = get_width_height(result_obj)[0]
        result_obj['height'] = get_width_height(result_obj)[1]

        all_results.append(result_obj)

    return all_results

conn = sqlite3.connect(options.sqlite)
c = conn.cursor()

all_groups = []
for row in c.execute("SELECT id, country, plate_number, frame_start, frame_end, confidence, region FROM plate_group ORDER BY frame_start ASC"):
    group_obj = {
        'id': int(row[0]),
        'country': row[1],
        'plate_number': row[2],
        'frame_start': int(row[3]),
        'frame_end': int(row[4]),
        'confidence': float(row[5]),
        'region': row[6]
    }

    all_groups.append(group_obj)

video_clip = VideoFileClip(options.video)
w,h = moviesize = video_clip.size
fps = video_clip.fps
print ("FPS: " + str(video_clip.fps))

print ("Available fonts: ")
print (TextClip.list('font'))


def get_smoothed_data(group):

    plates_for_group = get_plates_for_group(group['id'])
    for plate in plates_for_group:
        print ("%s: frame_num: %d" % (group['plate_number'], plate['frame_num']))
    smoothed_data = FrameSmoother(group, plates_for_group)

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

for group in all_groups:

    print (" -- ")
    print (group['plate_number'])
    print (" --")

    plate_number = group['plate_number']
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
    txt_mov = get_text_clip(group, smoothed_data, plate_number)
    composites.append(txt_mov)


    # add an insert effect at t + 2 frame
    effect_time = time_start + smoothed_data.frame_to_time(fps, 2)
    painting_fade = get_insert_effect(group, effect_time, smoothed_data)
    print ("Getting effect for %f" % (effect_time))
    if painting_fade is not None:
        inserts.append((effect_time, painting_fade))

    sound_clippy = get_audio_insert(group_count, time_start)
    if sound_clippy is not None:
        audio_track.append(sound_clippy)

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

all_audio = CompositeAudioClip(audio_track).set_fps(44100).set_duration(final.duration)

if options.time_end == 0:
    options.time_end = final.duration
final = final.set_audio(all_audio).subclip(options.time_start, options.time_end)

if options.preview:
    final.preview()
else:
    final.write_videofile(options.output_video, fps=30, codec='libx264')