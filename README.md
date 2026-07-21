# DMX USB Sandbox

This repo contains a minimal Python starter for driving a DMX fixture from a USB-to-DMX cable that behaves like an FTDI/Open-DMX style serial interface.

## Is this possible?

Yes, probably. The cable you linked is advertised as an FT232RL-based USB-to-RS485 DMX interface, which is the same general approach used by low-cost Open DMX style adapters. That means a script can usually drive it by:

1. Opening the cable's COM port.
2. Sending DMX timing with a break and mark-after-break.
3. Writing a 513-byte DMX packet: start code plus 512 channel values.

The main caveat is that cheap DMX cables are not always protocol-identical. Some work as a plain serial/Open-DMX interface, others only work reliably with specific software or drivers. This starter assumes the cable appears as a normal serial port on Windows.

## What this repo gives you

- `dmx_usb.py`: a small DMX sender for FTDI/Open-DMX style cables.
- `ports` command: list serial ports so you can find the DMX adapter.
- `set` command: set one or more channel values and keep streaming them.
- `blackout` command: send all DMX channels to zero.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Plug in the USB-to-DMX cable and confirm it shows up as a serial port:

```powershell
python dmx_usb.py ports
```

Typical output will look like:

```text
COM3: USB Serial Port
```

## First test

Set your Chauvet fixture to DMX mode and give it a start address, usually `001` for initial testing.

Then try sending a single channel to full:

```powershell
python dmx_usb.py set --port COM3 --value 1=255 --duration 10
```

Or send multiple channels at once:

```powershell
python dmx_usb.py set --port COM3 --value 1=255 --value 2=128 --value 3=255 --duration 10
```

Blackout everything:

```powershell
python dmx_usb.py blackout --port COM3 --duration 3
```

## Suggested Chauvet LX-5 test workflow

Because fixture personalities vary by revision and mode, the safest way to start is:

1. Put the LX-5 into DMX mode.
2. Set its DMX start address to `001`.
3. Try one channel at a time from `1` upward.
4. Note what each channel does.
5. Build a fixture-specific helper once the channel map is confirmed.

For example:

```powershell
python dmx_usb.py set --port COM3 --value 1=255 --duration 5
python dmx_usb.py set --port COM3 --value 2=255 --duration 5
python dmx_usb.py set --port COM3 --value 3=255 --duration 5
python dmx_usb.py set --port COM3 --value 4=255 --duration 5
```

## Hardware notes

- This cable is likely fine for learning and basic control, but low-cost USB-DMX adapters can be inconsistent.
- If the fixture flickers or ignores updates, try a lower frame rate such as `--frame-rate 20`.
- If Windows does not install the driver automatically, install the FTDI driver.
- DMX output should go to the fixture's DMX input, and the fixture should be in DMX slave mode rather than standalone or sound-active mode.
- Some fixtures need a terminator at the end of the DMX chain for stable behavior.

## Next steps

Once you confirm which LX-5 channel controls which function, the next useful step is to add a small fixture profile or scene script with names like `shutter`, `gobo`, `rotation`, or `dimmer`, depending on the fixture's DMX map.