from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass, field

import serial
from serial.tools import list_ports


DMX_CHANNELS = 512
DMX_BAUDRATE = 250000
DMX_BREAK_SECONDS = 0.0002
DMX_MARK_AFTER_BREAK_SECONDS = 0.00002


@dataclass
class DmxUniverse:
    channels: bytearray = field(default_factory=lambda: bytearray(DMX_CHANNELS + 1))

    def set_channel(self, channel: int, value: int) -> None:
        if channel < 1 or channel > DMX_CHANNELS:
            raise ValueError(f"DMX channel must be between 1 and {DMX_CHANNELS}: {channel}")
        if value < 0 or value > 255:
            raise ValueError(f"DMX value must be between 0 and 255: {value}")
        self.channels[channel] = value

    def set_channels(self, pairs: dict[int, int]) -> None:
        for channel, value in pairs.items():
            self.set_channel(channel, value)

    def clear(self) -> None:
        for index in range(1, DMX_CHANNELS + 1):
            self.channels[index] = 0


class OpenDmxUsbController:
    def __init__(self, port: str, *, frame_rate: float = 30.0) -> None:
        self._serial = serial.Serial(
            port=port,
            baudrate=DMX_BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_TWO,
            timeout=0,
            write_timeout=1,
        )
        self.universe = DmxUniverse()
        self._frame_interval = 1.0 / frame_rate
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def close(self) -> None:
        self.stop()
        if self._serial.is_open:
            self._serial.close()

    def set_channel(self, channel: int, value: int) -> None:
        with self._lock:
            self.universe.set_channel(channel, value)

    def set_channels(self, pairs: dict[int, int]) -> None:
        with self._lock:
            self.universe.set_channels(pairs)

    def blackout(self) -> None:
        with self._lock:
            self.universe.clear()

    def send_frame(self) -> None:
        with self._lock:
            payload = bytes(self.universe.channels)

        self._serial.break_condition = True
        time.sleep(DMX_BREAK_SECONDS)
        self._serial.break_condition = False
        time.sleep(DMX_MARK_AFTER_BREAK_SECONDS)
        self._serial.write(payload)
        self._serial.flush()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            started = time.perf_counter()
            self.send_frame()
            elapsed = time.perf_counter() - started
            remaining = self._frame_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)


def parse_assignments(values: list[str]) -> dict[int, int]:
    assignments: dict[int, int] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"Expected CHANNEL=VALUE, got: {item}")
        channel_text, value_text = item.split("=", 1)
        assignments[int(channel_text)] = int(value_text)
    return assignments


def list_serial_ports() -> int:
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return 1

    for port in ports:
        print(f"{port.device}: {port.description}")
    return 0


def hold_output(controller: OpenDmxUsbController, duration: float | None) -> None:
    controller.start()
    if duration is None:
        print("Streaming DMX. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        print(f"Streaming DMX for {duration:.1f} seconds.")
        time.sleep(duration)
    controller.stop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send DMX512 data over a USB-to-DMX FTDI/Open-DMX style cable."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ports", help="List available serial ports.")

    set_parser = subparsers.add_parser("set", help="Set one or more DMX channels and stream them.")
    set_parser.add_argument("--port", required=True, help="Serial port name, for example COM3.")
    set_parser.add_argument(
        "--value",
        action="append",
        required=True,
        metavar="CHANNEL=VALUE",
        help="DMX assignment, for example 1=255. Repeat for multiple channels.",
    )
    set_parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="How long to stream values. Use 0 or a negative number to stream until Ctrl+C.",
    )
    set_parser.add_argument(
        "--frame-rate",
        type=float,
        default=30.0,
        help="Frames per second to transmit. Lower values reduce USB traffic.",
    )

    blackout_parser = subparsers.add_parser("blackout", help="Send all channels to zero.")
    blackout_parser.add_argument("--port", required=True, help="Serial port name, for example COM3.")
    blackout_parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="How long to stream blackout values.",
    )
    blackout_parser.add_argument(
        "--frame-rate",
        type=float,
        default=30.0,
        help="Frames per second to transmit.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ports":
        return list_serial_ports()

    if args.command == "set":
        assignments = parse_assignments(args.value)
        duration = args.duration if args.duration > 0 else None
        controller = OpenDmxUsbController(args.port, frame_rate=args.frame_rate)
        try:
            controller.set_channels(assignments)
            hold_output(controller, duration)
        finally:
            controller.close()
        return 0

    if args.command == "blackout":
        controller = OpenDmxUsbController(args.port, frame_rate=args.frame_rate)
        try:
            controller.blackout()
            hold_output(controller, args.duration)
        finally:
            controller.close()
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())