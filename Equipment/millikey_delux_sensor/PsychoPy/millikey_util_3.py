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
Utility and wrapper functions for the Millikey (Delux).

Add this file to the experiment directory and then import it into the experiment script:

import millikey_util_x.py as millikey_util

where x is the version of millikey_util_*.py to import.
"""

import os
import serial
import json
import time
from psychopy import core
import queue
import threading

# Trigger type constants
TRIG_RISING_SERIAL = 1  # Only generate RISING triggers
TRIG_FALLING_SERIAL = 2 # Only generate FALLING triggers
TRIG_BOTH_SERIAL = 4    # Generate both RISING and FALLING triggers

# Holds the current millikey serial connection, if any
mk_serial = None

rx_timeout = 0.0
rx_thread = None
run_rx_thread = True
read_rx_threaded = False
rx_data_queue = queue.Queue()

def _read_from_port(ser):
    global run_rx_thread, rx_data_queue, read_rx_threaded, rx_timeout

    while run_rx_thread:
        if read_rx_threaded:
            reading = ser.readline()
            if reading:
                try:
                    rx_data_queue.put(json.loads(reading[:-2]))
                except:
                    pass
        else:
            time.sleep(0.005)

def getSerialPorts():
    """
    Return a list of serial ports that have a device connected to them. This can be any serial device,
    not just Millikey's.

    @return: list of connectable serial ports
    """
    available = []
    if os.name == 'nt':  # Windows
        for i in range(1, 512):
            try:
                sport = 'COM' + str(i)
                s = serial.Serial(sport, baudrate=128000)
                available.append(sport)
                s.close()
            except (serial.SerialException, ValueError):
                pass
    else:  # Mac / Linux
        from serial.tools import list_ports
        available = [port[0] for port in list_ports.comports()]
    return available


def getMilliKeyDevices():
    """
    Return a list of MilliKey devices connected. Each entry in the list is a dict of that MilliKey's current
    configuration, including the serial port that the device is connected to.

    @return: list of MilliKey device configuration dict's
    """
    devices = []
    available = getSerialPorts()
    for p in available:
        try:
            mkey_sport = serial.Serial(p, baudrate=128000, timeout=1.0)
            while mkey_sport.readline():
                pass
            mkey_sport.write(b"GET CONFIG\n")
            rx_data = mkey_sport.readline()
            if rx_data:
                rx_data = rx_data[:-1].strip()
                try:
                    mkconf = json.loads(rx_data)
                    mkconf['port'] = p
                    devices.append(mkconf)
                except:
                    raise RuntimeError("ERROR: {}".format(rx_data))
            mkey_sport.close()
        except:
            pass
    return devices


def openMillikeySerialConnection(timeout=0.0, delux_required=True, threaded_rx=True):
    """
    Open a serial connection to the first MilliKey device found on the computer.

    If no MilliKey's are detected, a RuntimeError is raised.

    If delux_required = True, and detected MilliKey does not have light sensor attached, a RuntimeError is raised.
    If delux_required = True, and a MilliKey Delux is present, device trigger mode is set to 0 (no triggers).

    If threaded_rx is True, a separate thread is started and reads serial data when when startLightSensor() is called,
    until stopLightSensor() is called.

    @param timeout: sec timeout for serial read operations, default is 0.0, which means non-blocking reads
    @param delux_required: True = Millikey must have light sensor support. False = light sensor not required
    @param threaded_rx: True = Read light sensor triggers from a Thread. False = Read triggers in non-threaded mode
    @return: MilliKey serial.Serial connection instance
    """
    global rx_timeout, mk_serial, rx_thread, run_rx_thread
    rx_timeout = timeout
    
    millikeys = getMilliKeyDevices()
    if len(millikeys) == 0:
        raise RuntimeError("No Millikey device detected.")
    
    mk_serial = serial.Serial(millikeys[0]['port'], baudrate=128000, timeout=timeout)

    try:
        mk_serial.set_buffer_size(rx_size=12800)
    except:
        pass

    if delux_required:
        sendSerial(mk_serial, 'SET AIN_TRIG_MODE 0', is_json=False)
        ain_stats = sendSerial(mk_serial, "GET AIN_STATS")
        ain_res = ain_stats.get('res')
        if ain_res > 100:  # ain_res < 100 means light sensor is connected
            mk_serial.close()
            raise RuntimeError("Error Light Sensor is not connected to Analog Input Jack.")
        
    if threaded_rx is True:
        print("*Note: Using threaded serial read of MilliKey triggers.")
        run_rx_thread = True
        rx_thread = threading.Thread(target=_read_from_port, args=(mk_serial,))
        rx_thread.start()

    return mk_serial


def getMilliKeyTime():
    """
    Get the current MilliKey time, converted to seconds.

    @return: float
    """
    return int(sendSerial(mk_serial, "GET TIME", is_json=False))/1000.0/1000.0


def resetMilliKeyTimer():
    """
    Reset the MilliKey timer to 0.
    
    @return: None
    """
    mk_serial.write(b"SET TIME\n")


def closeMillikey():
    """
    Close the currently open MilliKey serial connection.

    @return: None
    """
    global mk_serial, rx_thread, run_rx_thread, read_rx_threaded

    if rx_thread:
        run_rx_thread = False
        read_rx_threaded = False
        rx_thread.join()

    if mk_serial:
        mk_serial.reset_input_buffer()
        mk_serial.close()


def sendSerial(sconn=None, txdata=None, wait=0.050, is_json=True):
    """
    Send 'txdata' command to a Millikey device using the serial connection 'sconn'.
    Then wait up to 'wait' seconds for a response from the device. If 'is_json' is True,
    the response is converted to a dict before being returned.

    @param sconn: Millikey serial connection
    @param txdata: MilliKey command to send
    @param wait: sec to wait trying to read a response from the MilliKey.
    @param is_json: True = convert str response to a dict, False = leave response as str
    @return: response read from MilliKey, or None if no response was received within wait seconds.
    """
    if sconn is None:
        sconn = mk_serial

    sconn.write("{}\n".format(txdata).encode('utf-8'))
    stime = core.getTime()
    rx = mk_serial.readline()
    while (len(rx) == 0 or rx[-2:] != b'\r\n') and core.getTime() - stime < wait:
        rx += mk_serial.readline()

    if len(rx) and rx[-2:] == b'\r\n':
        rx = rx[:-2]
    else:
        print("**WARNING: Incomplete serial response: [", rx, "]")

    if rx and is_json:
        try:
            return json.loads(rx)
        except Exception:
            return rx
    if rx:
        return rx


def startLightSensor():
    """
    Start the MilliKey Delux light sensor. After being started, the MilliKey
    can generate light triggers or samples.
    
    @return: None
    """
    global read_rx_threaded
    if rx_thread:
        read_rx_threaded = True
    mk_serial.write(b"START_AIN\n")


def stopLightSensor():
    """
    Stop the MilliKey Delux light sensor. The MilliKey Delux will no longer 
    generate light triggers or samples.
    
    @return: None
    """
    global read_rx_threaded
    mk_serial.write(b"STOP_AIN\n")
    if rx_thread:
        read_rx_threaded = False


def getLightSensorStats(pwin, stim):
    """
    Collect light sensor statistics while 'stim' is presented for 10 frames. Light sensor statistics are returned
    as a dict, of the form:

    {'min': 57,         # Minimum light sensor reading detected during stim presentation
     'max': 367,        # Max light sensor reading detected during stim presentation
     'reads': 838,      # Number of light sensor readings collected while analog output was enabled
     'mean': 148,       # Average light sensor reading detected during stim presentation
     'trig_cnt': 0,     # Number of light sensor triggers that occurred during stim presentation
     'max_trig_cnt': 0, # Maximum number of light sensor triggers Millikey will generate after starting the light sensor
     'res': 4           # Reserved: Used to detect if light sensor is connected to MilliKey device.
    }

    @param pwin: PsychoPy Window to display stim in
    @param stim: PsychoPy visual stimulus to be presented
    @return: dict of MilliKey light sensor stats
    """
    global mk_serial
    for i in range(4):
        stim.draw()
        pwin.flip()
    mk_serial.write(b"START_AIN\n")
    for i in range(10):
        stim.draw()
        pwin.flip()
    mk_serial.write(b"STOP_AIN\n")

    return sendSerial(mk_serial, "GET AIN_STATS", wait=0.1, is_json=True)


def autoThresholdLightSensor(win, white_stim, dark_stim, rising_thresh_multiplier=0.5, falling_thresh_multiplier=0.5):
    """
    Run an automated thresholding procedure for the MilliKey Delux light sensor. Light sensor data collected during
    the alternating presentation of white_stim and dark_stim. This data is used to set the light sensor's rising
    and falling threshold levels (rising_threshold_level, falling_threshold_level) using the
    rising_thresh_multiplier and falling_thresh_multiplier provided.

    Note: rising_thresh_multiplier must always be <= falling_thresh_multiplier.

    rising_threshold_level = lowlight_stats['max'] + light_range * rising_thresh_multiplier
    falling_threshold_level = lowlight_stats['max'] + light_range * falling_thresh_multiplier

    where bright_stats is the light sensor stats dict returned by getLightSensorStats when white_stim is presented,
          lowlight_stats is the light sensor stats dict returned by getLightSensorStats when dark_stim is presented,
          light_range = bright_stats['max'] - lowlight_stats['max']

    The MilliKey Delux is programmed to use the calculated rising_threshold_level, falling_threshold_level.

    @param win: PsychoPy window
    @param white_stim: light / bright stimulus to use for thresholding. rgb8 of 255,255,255 is suggested.
    @param dark_stim: dark / dim stimulus to use for thresholding. rgb8 of 0,0,0 is suggested.
    @param rising_thresh_multiplier: multiplier used in calculating rising_threshold_level. Must be > 0 and < 1
    @param falling_thresh_multiplier:  multiplier used in calculating falling_threshold_level. Must be > 0 and < 1
    @return: rising_threshold_level, falling_threshold_level
    """
    global mk_serial

    dark_stim.draw()
    win.flip()
    dark_stim.draw()
    win.flip()
    lowlight_stats = getLightSensorStats(win, dark_stim)

    white_stim.draw()
    win.flip()
    white_stim.draw()
    win.flip()
    bright_stats = getLightSensorStats(win, white_stim)

    light_range = bright_stats.get('max') - lowlight_stats.get('max')
    ls_threshold = lowlight_stats.get('max') + light_range * rising_thresh_multiplier
    hs_threshold = lowlight_stats.get('max') + light_range * falling_thresh_multiplier
    print(sendSerial(mk_serial, "SET AIN_THRESHOLD %d %d" % (ls_threshold, hs_threshold)))

    dark_stim.draw()
    win.flip()

    return ls_threshold, hs_threshold


def setLightSensorParams(trig_delay=0, min_threshold_count=1, trig_types=TRIG_BOTH_SERIAL, max_trig_count=0):
    """
    Set various Millikey Delux light sensor parameters. Default values must be used for ELMB monitors, and are suggested
    in general.

    trigger delay, minimum sample count needed for a trigger, trigger types to
    create, and maximum trigger count
    @param trig_delay: Number of msec the Millikey waits to send a trigger event after the trigger actually occurred.
    @param min_threshold_count: Number of samples (10 / msec) that the light sensor must be in previous state for a trigger to be generated.
    @param trig_types: Either TRIG_RISING_SERIAL, TRIG_FALLING_SERIAL, or TRIG_BOTH_SERIAL (default)
    @param max_trig_count: Maximum number of light sensor triggers the Millikey will generate after the light sensor is started. 0 = unlimited triggers.
    @return: None
    """
    global mk_serial
    print(sendSerial(mk_serial, 'SET AIN_TRIG_DELAY %d'%(trig_delay), is_json=False))
    print(sendSerial(mk_serial, 'SET AIN_MIN_THRESH_COUNT %d'%(min_threshold_count), is_json=False))
    print(sendSerial(mk_serial, 'SET AIN_TRIG_MODE %d %d'%(trig_types, max_trig_count), is_json=False))

# def clearSerialData():
#     """
#     Clear all serial rx data from the MilliKey serial connection.
#
#     @return: None
#     """
#     mk_serial.reset_input_buffer()

def getNextLightTrigger(timeout=0):
    """
    Wait for, at most timeout seconds, for the next light sensor trigger.
    Return it if found.
    
    @return: trigger_dict, trigger_time
    """
    trigger_time = trigger_dict = None

    # If threaded rx reading is enabled, read from rx_data_queue
    if read_rx_threaded:
        try:
            if timeout == 0:
                trigger_dict = rx_data_queue.get_nowait()
            else:
                trigger_dict = rx_data_queue.get(timeout=timeout)
        except queue.Empty:
            pass
        if trigger_dict:
            trigger_time = trigger_dict['time'] / 1000 / 1000
        return trigger_dict, trigger_time

    # If threaded rx reading is disabled, read from serial connection mk_serial
    trigger_dict = mk_serial.readline()
    stime = core.getTime()
    while not trigger_dict and (core.getTime() - stime) <= timeout:
        trigger_dict = mk_serial.readline()
    if trigger_dict:
        trigger_dict = json.loads(trigger_dict[:-2])
        trigger_time = trigger_dict['time']/1000/1000
    else:
        trigger_time = None
    return trigger_dict, trigger_time

