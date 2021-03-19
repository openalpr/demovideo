import numpy

class FrameSmoother():
    def __init__(self, group, plates):
        self.group = group
        self.plates = plates

        self.plates_by_frame = {}

        self.positions = {}

        self._organize_plates_by_frame()

        for k,v in self.plates_by_frame.items():
            print (k)
        self.fill_missing_frames()

        self.smooth_frames()

    # Fill a dictionary indexed by frame number
    def _organize_plates_by_frame(self):
        for plate in self.plates:
            self.plates_by_frame[plate['f']] = plate


    # Fill the interstitial frames where no plate was found
    def fill_missing_frames(self):
        frame_start = self.group['frame_start']
        frame_end = self.group['frame_end']

        for i in range(frame_start, frame_end + 1):

            if i not in self.plates_by_frame and i not in self.positions:
                # This frame is missing, fill it in
                q = i
                while q not in self.plates_by_frame:
                    q += 1

                next_valid_frame = q
                next_center = (self.plates_by_frame[q]['center_x'], self.plates_by_frame[q]['center_y'])

                previous_valid_frame = i-1
                last_center = (self.plates_by_frame[previous_valid_frame]['center_x'], self.plates_by_frame[previous_valid_frame]['center_y'])

                x_diff = next_center[0] - last_center[0]
                y_diff = next_center[1] - last_center[1]
                frames_missing = q - i
                print ("XDIFF: %d  YDIFF: %d   Frames_missing: %d" % (x_diff, y_diff, frames_missing))
                q = i
                while q not in self.plates_by_frame:

                    my_center_x = (float(x_diff) / float(frames_missing + 1)) * float(q - i + 1) + last_center[0]
                    my_center_y = (float(y_diff) / float(frames_missing + 1)) * float(q - i + 1) + last_center[1]

                    self.positions[q] = {
                        'center_x': round(my_center_x, 0),
                        'center_y': round(my_center_y, 0)
                    }
                    print ("%d: Interpolated center: %d, %d" % (q, my_center_x, my_center_y))
                    q += 1


            elif i not in self.positions:

                self.positions[i] = {
                    'center_x': self.plates_by_frame[i]['center_x'],
                    'center_y': self.plates_by_frame[i]['center_y']
                }
                print ("%d: No interpolation: %d, %d" %(i, self.plates_by_frame[i]['center_x'], self.plates_by_frame[i]['center_y']))

                #last_slope =
                #last_center = (self.positions[i]['center_x'], self.positions[i]['center_y'])

            #print i



    def savitzky_golay(self, y, window_size, order, deriv=0, rate=1):

        import numpy as np
        from math import factorial

        try:
            window_size = np.abs(np.int(window_size))
            order = np.abs(np.int(order))
        except ValueError:
            raise ValueError("window_size and order have to be of type int")
        if window_size % 2 != 1 or window_size < 1:
            raise TypeError("window_size size must be a positive odd number")
        if window_size < order + 2:
            raise TypeError("window_size is too small for the polynomials order")
        order_range = range(order+1)
        half_window = (window_size -1) // 2
        # precompute coefficients
        b = np.mat([[k**i for i in order_range] for k in range(-half_window, half_window+1)])
        m = np.linalg.pinv(b).A[deriv] * rate**deriv * factorial(deriv)
        # pad the signal at the extremes with
        # values taken from the signal itself
        firstvals = y[0] - np.abs( y[1:half_window+1][::-1] - y[0] )
        lastvals = y[-1] + np.abs(y[-half_window-1:-1][::-1] - y[-1])
        y = np.concatenate((firstvals, y, lastvals))
        return np.convolve( m[::-1], y, mode='valid')

    def smooth_frames(self, delta=13):
        # Assuming the frames have been interpolated, now we smooth the x/y coordinates
        x_grid = []
        y_grid = []


        for k in sorted(self.positions):
            v = self.positions[k]

            x_grid.append(v['center_x'])
            y_grid.append(v['center_y'])


        while len(x_grid) < delta:
            delta -= 2

        try:
            self.smoothed_x = self.savitzky_golay(numpy.array(x_grid), delta, 3)
            self.smoothed_y = self.savitzky_golay(numpy.array(y_grid), delta, 3)
        except:
            self.smoothed_x = x_grid
            self.smoothed_y = y_grid
        #self.smoothed_x = self.smooth(numpy.array(x_grid), window_len=delta, window='flat')
        #self.smoothed_y = self.smooth(numpy.array(y_grid), window_len=delta, window='flat')

        index = 0
        for k in sorted(self.positions):
            v = self.positions[k]
            plate_number = ''
            if 'best_plate_number' in self.group:
                plate_number = self.group['best_plate_number']
            print ("%s: %d: orig: %d, %d -- smoothed: %f, %f -- rounded: %f, %f" % (plate_number, k, self.positions[k]['center_x'], self.positions[k]['center_y'],
                                                            self.smoothed_x[index], self.smoothed_y[index], round(self.smoothed_x[index], 0), round(self.smoothed_y[index], 0)))
            index += 1

    def frame_to_time(self, fps, frame):
        return float(frame) / float(fps)

    def time_to_frame(self, fps, time):
        return int(float(fps) * float(time))

    def get_smoothed_xy_at(self, fps, time):
        frame_num = self.time_to_frame(fps, time)

        smoothed_index = frame_num - self.group['frame_start']

        plate_number = ''
        if 'best_plate_number' in self.group:
            plate_number = self.group['best_plate_number']

        if smoothed_index < 0 or smoothed_index > len(self.smoothed_x) or frame_num < self.group['frame_start'] or frame_num > self.group['frame_end']:
            return (-100, -100)

        print ("%s: %f - frame %d - index %d - x/y: %d, %d" % (plate_number, time, frame_num, smoothed_index, self.smoothed_x[smoothed_index], self.smoothed_y[smoothed_index]))
        return (round(self.smoothed_x[smoothed_index], 0),
                round(self.smoothed_y[smoothed_index], 0))

