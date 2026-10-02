#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
"""
Test visual stim onset and duration timing using the MilliKey light sensor.

This example uses the MilliKey timer and the light trigger 'time' field to read trigger times.
This functionality was added in MilliKey firmware version 1.5.5, so 1.5.5 or above is required.

To open a serial connection to the first MilliKey detected on the computer call

    millikey_util.openMillikeySerialConnection()

Once a MilliKey connection is open, the MilliKey light sensor can be calibrated to generate a RISING trigger
when a dark -> light screen brightness change is detected, and a FALLING trigger when a light -> dark screen
brightness change is detected. Use

    millikey_util.autoThresholdLightSensor(...)

to auto threshold the light sensor trigger levels used for RISING and FALLING triggers. Then call

    millikey_util.setLightSensorParams()

to set the MilliKey light sensor parameters, with defaults of:

    trig_delay=0                # No trigger delay
    min_threshold_count=1       # 1 light sensor sample is enough to generate a trigger
    trig_types=TRIG_BOTH_SERIAL # Generate both RISING and FALLING triggers
    max_trig_count=0            # Generate unlimited number of triggers while light sensor is active

Defaults should be sufficient for most use cases. Always use the defaults when an ELMB monitor is being tested.

See the runTrial(...) function below as an example of starting the light sensor, collecting light sensor triggers,
and then stopping the light sensor for each trial of the demo.

At the end of the experiment, remember to close the MilliKey serial connection:

millikey_util.closeMillikey()

"""
import millikey_util_3 as millikey_util
from psychopy import core, visual, event
import numpy

trial_count = 10

autothresh_millikey = True
rising_thresh_multiplier = falling_thresh_multiplier = 0.5

check_for_reading_timeout = 0.05


def runTrial(trial_num, win, background_stim, test_stim):
    print("** Running Trial:", trial_num)
    background_stim.draw()
    win.flip()

    # MILLIKEY: Turn on the MilliKey light sensor (start generating light triggers)
    millikey_util.startLightSensor()

    test_stim.draw()

    # MILLIKEY: Set the MilliKey timer to 0 on the next window flip (when the test stim is first displayed)
    win.callOnFlip(millikey_util.resetMilliKeyTimer)

    # draw the white test stim
    on_ftime = win.flip()

    # leave the white test stim visible for trial_num * 0.01 seconds
    core.wait((trial_num+1) * 0.01)

    # remove the white test stim
    background_stim.draw()
    off_ftime = win.flip()

    # MILLIKEY: Get all light sensor triggers that occurred during stim presentation,
    # until no triggers are read for check_for_reading_timeout seconds
    triggers = []
    trig, trig_time = millikey_util.getNextLightTrigger(check_for_reading_timeout)
    while trig:
        triggers.append((trig_time, trig))
        trig, trig_time = millikey_util.getNextLightTrigger(check_for_reading_timeout)

    # MILLIKEY: Turn off the MilliKey light sensor (stop generating light triggers)
    millikey_util.stopLightSensor()

    # Get first and last triggers
    on_reading = off_reading = None
    on_ttime = off_ttime = None
    if len(triggers) > 0:
        on_ttime, on_reading = triggers[0]
    if len(triggers) > 1:
        off_ttime, off_reading = triggers[-1]

    # print results for trial
    if on_reading is None or off_reading is None:
        print("WARNING: No start and/or end light triggers read for trial %d." % (trial_num))
    else:
        stim_onset_delay = on_ttime*1000
        flip_stim_dur = (off_ftime - on_ftime) * 1000
        actual_dur = (off_ttime - on_ttime) * 1000
        print('stim_onset_delay:', stim_onset_delay)
        print('flip_stim_dur:', flip_stim_dur)
        print('trigger_stim_dur:', actual_dur)
        print('stim_dur_diff:', actual_dur - flip_stim_dur)
        print('on_trigger:', on_reading)
        print('off_trigger:', off_reading)

    core.wait(0.25)


if __name__ == "__main__":
    # MILLIKEY: Open serial connection to MilliKey device
    # threaded_rx=True: Use threaded reading of Millikey triggers when light sensor is active.
    millikey_util.openMillikeySerialConnection(threaded_rx=True)

    # Create PsychoPy window and test stim
    win = visual.Window(fullscr=True, screen=0, color=(-1, -1, -1))

    print("win_frame_rate: ", 1000.0 / win.getActualFrameRate() / 1000.0)

    white_stim = visual.ShapeStim(win, lineColor='white', fillColor='white',
                                  vertices=((-1, -1), (1, -1), (1, 1), (-1, 1)))
    dark_stim = visual.ShapeStim(win, lineColor='black', fillColor='black',
                                 vertices=((-1, -1), (1, -1), (1, 1), (-1, 1)))

    txt_stim1 = visual.TextStim(win, "Place DeLux Light Sensor in Top Left Corner.",
                                color=(0.0, 1.0, 0.0), height=0.05)
    txt_stim2 = visual.TextStim(win, "Press any Key to Start Test.", pos=(0.0, -0.1),
                                color=(0.0, 1.0, 0.0), height=0.05)

    white_stim.draw()
    dark_stim.draw()
    txt_stim1.draw()
    txt_stim2.draw()
    win.flip()

    # wait for keypress before starting MilliKey auto threshold
    start_key = event.waitKeys()

    # MILLIKEY: Auto threshold MilliKey light sensor
    if autothresh_millikey:
        millikey_util.autoThresholdLightSensor(win, white_stim, dark_stim,
                                               rising_thresh_multiplier,
                                               falling_thresh_multiplier)

    # MILLIKEY: Set MilliKey params for light sensor (trigger type, etc)
    millikey_util.setLightSensorParams()


    # Run block of trials
    for t in range(trial_count):
        runTrial(t, win, dark_stim, white_stim)

    # MILLIKEY: Close MilliKey serial connection
    millikey_util.closeMillikey()

    # End experiment
    win.close()
    core.quit()
