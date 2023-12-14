import pymumble_py3
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED as PCS
import pyaudio
import audioop
import argparse
import time
import sys
import serial
from threading import Lock
import threading
import os

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

parser = argparse.ArgumentParser(
                    prog='mumblerf',
                    description='Connects digirig to mumble')

parser.add_argument('--vox-level',default=100,type=int)
parser.add_argument('--vox-start-delay-ms',default=50,type=int)
parser.add_argument('--vox-end-delay-ms',default=1000,type=int)
parser.add_argument('--mumble-to-rf-tail',default=100,type=int)
parser.add_argument('--sample-rate',default=48000,type=int)
parser.add_argument('--tot-seconds',default=300,type=int)
parser.add_argument('--input-device', required='--list-audio-devices' not in sys.argv)
parser.add_argument('--output-device', required='--list-audio-devices' not in sys.argv)
parser.add_argument('--report-level',action='store_true',default=False)
parser.add_argument('--list-audio-devices',action='store_true',default=False)
parser.add_argument('--serial-port', required='--list-audio-devices' not in sys.argv)
parser.add_argument('--audio-out-multiplier', default=1, type=float)


parser.add_argument('--mumble-address',default="localhost",type=str)
parser.add_argument('--mumble-port',default=64738,type=int)
parser.add_argument('--mumble-nick',default="radio",type=str)
parser.add_argument('--mumble-password',default="",type=str)

args = parser.parse_args()



# pyaudio set up
CHUNK = 2048
FORMAT = pyaudio.paInt16  # pymumble soundchunk.pcm is 16 bits
CHANNELS = 1
RATE = args.sample_rate  # pymumble soundchunk.pcm is 48000Hz
BYTES_PER_FRAME = pyaudio.get_sample_size(FORMAT)

p = pyaudio.PyAudio()


info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')

input_devices = {}
output_devices = {}

for i in range(0, numdevices):
    if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
        input_devices[p.get_device_info_by_host_api_device_index(0, i).get('name')] = i
    if (p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels')) > 0:
        output_devices[p.get_device_info_by_host_api_device_index(0, i).get('name')] = i

if args.list_audio_devices:
    print("Input devices:")
    for x in input_devices:
        print(f"  {input_devices[x]} - {x}")
    print("Output devices:")
    for x in output_devices:
        print(f"  {output_devices[x]} - {x}")
    sys.exit()

try:
    input_device_index = int(args.input_device)
except ValueError:
    try:
        input_device_index = input_devices[args.input_device]
    except KeyError:
        raise KeyError(f"Could not find input sound card with label {args.input_device}")

try:
    output_device_index = int(args.output_device)
except ValueError:
    try:
        output_device_index = output_devices[args.output_device]
    except KeyError:
        raise KeyError(f"Could not find output sound card with label {args.output_device}")
    
rf_tx_sample_state = None
rf_rx_sample_state = None

input_stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,  # enable both talk
                output=False,  # and listen
                frames_per_buffer=CHUNK,
                input_device_index=input_device_index
                )


rf_tx = False
last_tx = None



def set_ptt(ser, state):
    ser.rts = state
    ser.dtr = state

ser = serial.Serial(args.serial_port)
set_ptt(ser,False)


talking_user = None
audio_buffer = b''
audio_buffer_lock = Lock()
output_lock = Lock()

def tot():
    global ser
    start_tx = None
    while 1:
        time.sleep(0.1)
        check_tx = ser.rts or ser.dtr
        if check_tx:
            if not start_tx:
                print("TOT: detected start of TX")
                start_tx = time.monotonic()
            if start_tx + args.tot_seconds < time.monotonic():
                print("TOT: Detected issue")
                ser.rts = False
                ser.dtr = False
                print("TOT: disabled serial")
                os._exit(1)
        else:
            if start_tx:
                start_tx = None
                print("TOT: disarmed")


            
tot_thread = threading.Thread(target=tot)
tot_thread.start()
        


# mumble client set up
def sound_received_handler(user, soundchunk):
    """ play sound received from mumble server upon its arrival """
    global audio_buffer, audio_buffer_lock, talking_user, rf_tx_sample_state
    with audio_buffer_lock:
        (audio_sample, rf_tx_sample_state) = audioop.ratecv(soundchunk.pcm,BYTES_PER_FRAME,CHANNELS,pymumble_py3.constants.PYMUMBLE_SAMPLERATE, RATE, rf_tx_sample_state)
        if not talking_user:
            talking_user = user['hash']
        if talking_user == user['hash']:
            audio_buffer += audio_sample



def play_sound(in_data, frame_count, time_info, status):
    global audio_buffer, rf_tx, last_tx, ser, talking_user

    buffer_size = frame_count * BYTES_PER_FRAME
    output = bytearray(buffer_size)
    with audio_buffer_lock:
        bytes_to_pull = min(buffer_size,len(audio_buffer))
        output[:bytes_to_pull] = audio_buffer[:bytes_to_pull]
        audio_buffer = audio_buffer[bytes_to_pull:]
    if output != bytearray(buffer_size):
        if not rf_tx:
                    set_ptt(ser, True)
                    print("rf txing")
                    rf_tx = True
        last_tx = time.monotonic()
    if last_tx and time.monotonic() - last_tx > (args.mumble_to_rf_tail/1000):
        print("stop rf tx")
        rf_tx = False
        last_tx = None
        talking_user = None
        set_ptt(ser, False)
        with audio_buffer_lock:
            talking_user = None
    
    output = bytes(output) # convert to bytes

    # adjust volume
    output = audioop.mul(output,BYTES_PER_FRAME, args.audio_out_multiplier)
    return (output, pyaudio.paContinue)
    
output_stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=False,  # enable both talk
                output=True,  # and listen
                frames_per_buffer=CHUNK,
                output_device_index=output_device_index,
                stream_callback=play_sound
                )


def _set_bandwidth(bandwidth):
    return

# Spin up a client and connect to mumble server
mumble = pymumble_py3.Mumble(args.mumble_address, args.mumble_nick, password=args.mumble_password, port=args.mumble_port, debug=False)

# monkley patch as setting and reading bandwidth doesn't seem to work on macos
pymumble_py3.mumble.soundoutput.SoundOutput._set_bandwidth = _set_bandwidth

#mumble.bandwidth = 48000
# set up callback called when PCS event occurs
mumble.callbacks.set_callback(PCS, sound_received_handler)
mumble.set_receive_sound(1)  # Enable receiving sound from mumble server
mumble.start()
mumble.is_ready()  # Wait for client is ready



# constant capturing sound and sending it to mumble server
counter = 0
max_audio = 0
vox_detect = None
vox_end_detect = None
buffer_reached = None
tx = False
while True:
    data = input_stream.read(CHUNK * BYTES_PER_FRAME, exception_on_overflow=False)
    (data, rf_rx_sample_state) = audioop.ratecv(data,BYTES_PER_FRAME,CHANNELS,RATE, pymumble_py3.constants.PYMUMBLE_SAMPLERATE, rf_rx_sample_state)
    reading = audioop.max(data, BYTES_PER_FRAME)
    # handle printing out levels for debugigng
    if reading > max_audio:
        max_audio = reading
    counter += 1
    if args.vox_level and counter > 10:
        counter = 0
        print(f"max audio level = {max_audio}")
        max_audio=0

    # vox  detection
    if reading > args.vox_level and not vox_detect and not tx and not rf_tx:
        print(f"vox threshold reached: {counter}")
        vox_detect = time.monotonic()
    elif reading > args.vox_level:
        pass
    else:
        vox_detect = None

    if (
            vox_detect and
            time.monotonic() - vox_detect > (args.vox_start_delay_ms/1000)
            and not tx
        ):
        print(f"starting tx to mumble: {counter}")
        tx = True

    if tx and reading < args.vox_level:
        if not vox_end_detect:
            print("vox level low")
            vox_end_detect = time.monotonic()
        elif time.monotonic() - vox_end_detect > (args.vox_end_delay_ms/1000):
            print("Stopping tx to mumble")
            tx = False
            vox_end_detect = None
    else:
        vox_end_detect = None

    if rf_tx: # handles when someone in the channel is transmitting
        vox_end_detect = None
        vox_detect = None
        tx = False

    if tx:
        mumble.sound_output.add_sound(data)