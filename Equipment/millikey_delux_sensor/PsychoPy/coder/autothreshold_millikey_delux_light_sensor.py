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
Run an auto threshold roiutine for the Millikey Delux light sensor.
"""
import millikey_util_3 as millikey_util
from psychopy import core, visual, event
import numpy

rising_thresh_multiplier = falling_thresh_multiplier = 0.5
check_for_reading_timeout = 0.05

if __name__ == "__main__":
    # MILLIKEY: Open serial connection to MilliKey device
    # threaded_rx=True: Use threaded reading of Millikey triggers when light sensor is active.
    millikey_util.openMillikeySerialConnection(threaded_rx=False)

    # Create PsychoPy window and test stim
    win = visual.Window(fullscr=True, screen=0, color=(-1, -1, -1))

    print("win_frame_rate: ", 1000.0 / win.getActualFrameRate() / 1000.0)

    white_stim = visual.ShapeStim(win, lineColor='white', fillColor='white',
                                  vertices=((-1, -1), (1, -1), (1, 1), (-1, 1)))
    dark_stim = visual.ShapeStim(win, lineColor='black', fillColor='black',
                                 vertices=((-1, -1), (1, -1), (1, 1), (-1, 1)))

    txt_stim1 = visual.TextStim(win, "Place DeLux Light Sensor in Top Left Corner.",
                                color=(0.0, 1.0, 0.0), height=0.05)
    txt_stim2 = visual.TextStim(win, "Press any Key When Ready.", pos=(0.0, -0.1),
                                color=(0.0, 1.0, 0.0), height=0.05)

    white_stim.draw()
    dark_stim.draw()
    txt_stim1.draw()
    txt_stim2.draw()
    win.flip()

    # wait for keypress before starting MilliKey auto threshold
    start_key = event.waitKeys()

    # MILLIKEY: Auto threshold MilliKey light sensor
    millikey_util.autoThresholdLightSensor(win, white_stim, dark_stim,
                                           rising_thresh_multiplier,
                                           falling_thresh_multiplier)

    # MILLIKEY: Close MilliKey serial connection
    millikey_util.closeMillikey()

    # End experiment
    win.close()
    core.quit()
