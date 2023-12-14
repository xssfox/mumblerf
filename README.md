Bridges a mumble server to RF using a sound card that has serial rts ptt control. Uses VOX for signal detection


```sh
usage: mumblerf [-h] [--vox-level VOX_LEVEL] [--vox-start-delay-ms VOX_START_DELAY_MS] [--vox-end-delay-ms VOX_END_DELAY_MS] [--mumble-to-rf-tail MUMBLE_TO_RF_TAIL]
                      [--sample-rate SAMPLE_RATE] [--tot-seconds TOT_SECONDS] --input-device INPUT_DEVICE --output-device OUTPUT_DEVICE [--report-level] [--list-audio-devices]
                      --serial-port SERIAL_PORT [--audio-out-multiplier AUDIO_OUT_MULTIPLIER] [--mumble-address MUMBLE_ADDRESS] [--mumble-port MUMBLE_PORT] [--mumble-nick MUMBLE_NICK]
                      [--mumble-password MUMBLE_PASSWORD]

Connects digirig to mumble

optional arguments:
  -h, --help            show this help message and exit
  --vox-level VOX_LEVEL
  --vox-start-delay-ms VOX_START_DELAY_MS
  --vox-end-delay-ms VOX_END_DELAY_MS
  --mumble-to-rf-tail MUMBLE_TO_RF_TAIL
  --sample-rate SAMPLE_RATE
  --tot-seconds TOT_SECONDS
  --input-device INPUT_DEVICE
  --output-device OUTPUT_DEVICE
  --report-level
  --list-audio-devices
  --serial-port SERIAL_PORT
  --audio-out-multiplier AUDIO_OUT_MULTIPLIER
  --mumble-address MUMBLE_ADDRESS
  --mumble-port MUMBLE_PORT
  --mumble-nick MUMBLE_NICK
  --mumble-password MUMBLE_PASSWORD

python3 mumblerf.py --input-device USB PnP Sound Device: Audio (hw:1,0) --output-device USB PnP Sound Device: Audio (hw:1,0) --report-level --serial-port /dev/ttyUSB0 --vox-level 100 --audio-out-multiplier 0.5
```

