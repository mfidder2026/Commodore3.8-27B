"""Run a .prg in VICE and read back the screen over the binary monitor protocol.

The emulator is started with autostart + warp and polled: each poll pauses the
machine, reads screen RAM, and resumes it. A run ends when BASIC prints
``ready.`` after the autostart ``run``, when a BASIC error appears, when the
CPU jams (VICE is told to quit), or when the wall-clock timeout expires
(normal for programs that loop forever, such as games and raster effects).
"""

from __future__ import annotations

import re
import socket
import struct
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Toolchain, load_toolchain
from .petscii import screen_to_lines
from .platforms import Platform

STX = 0x02
API_VERSION = 0x02
CMD_MEMORY_GET = 0x01
CMD_BANKS_AVAILABLE = 0x82
CMD_EXIT = 0xAA
CMD_QUIT = 0xBB
EVENT_ID = 0xFFFFFFFF

_BASIC_ERROR = re.compile(r"^\?.*error")


class MonitorError(RuntimeError):
    pass


class BinaryMonitor:
    """Minimal client for the VICE binary monitor (API version 2)."""

    def __init__(self, port: int, connect_timeout: float = 20.0):
        deadline = time.monotonic() + connect_timeout
        while True:
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise MonitorError(f"could not connect to VICE binary monitor on port {port}")
                time.sleep(0.2)
        self._next_id = 1

    def close(self) -> None:
        self.sock.close()

    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise MonitorError("VICE closed the monitor connection")
            buf.extend(chunk)
        return bytes(buf)

    def _read_response(self) -> tuple[int, int, int, bytes]:
        header = self._recv_exact(12)
        stx, _api, length, rtype, error, req_id = struct.unpack("<BBIBBI", header)
        if stx != STX:
            raise MonitorError(f"bad response start byte {stx:#x}")
        return rtype, error, req_id, self._recv_exact(length)

    def command(self, cmd: int, body: bytes = b"") -> bytes:
        req_id = self._next_id
        self._next_id += 1
        self.sock.sendall(struct.pack("<BBIIB", STX, API_VERSION, len(body), req_id, cmd) + body)
        while True:
            rtype, error, rid, payload = self._read_response()
            if rid == EVENT_ID or rid != req_id:
                continue  # async events (stopped/resumed/checkpoint) are not needed here
            if error:
                raise MonitorError(f"monitor command {cmd:#x} failed with error {error:#x}")
            return payload

    def banks(self) -> dict[str, int]:
        payload = self.command(CMD_BANKS_AVAILABLE)
        count, = struct.unpack_from("<H", payload, 0)
        pos, banks = 2, {}
        for _ in range(count):
            size = payload[pos]
            bank_id, name_len = struct.unpack_from("<HB", payload, pos + 1)
            banks[payload[pos + 4:pos + 4 + name_len].decode()] = bank_id
            pos += 1 + size
        return banks

    def read_memory(self, start: int, end: int, bank: int = 0) -> bytes:
        body = struct.pack("<BHHBH", 0, start, end, 0, bank)
        payload = self.command(CMD_MEMORY_GET, body)
        length, = struct.unpack_from("<H", payload, 0)
        return payload[2:2 + length]

    def resume(self) -> None:
        self.command(CMD_EXIT)

    def quit(self) -> None:
        try:
            self.command(CMD_QUIT)
        except (MonitorError, OSError):
            pass


@dataclass
class RunResult:
    status: str                       # "finished" | "basic_error" | "timeout" | "jam" | "error"
    screen: list[str] = field(default_factory=list)
    seconds: float = 0.0
    detail: str = ""
    memory: dict[int, int] = field(default_factory=dict)   # requested peeks at the end of the run

    @property
    def screen_text(self) -> str:
        return "\n".join(self.screen)

    def output_lines(self) -> list[str]:
        """Screen lines printed by the program: after the autostart 'run' line, before the final 'ready.'."""
        lines = self.screen
        start = max((i for i, l in enumerate(lines) if l.strip() == "run"), default=-1) + 1
        out = lines[start:]
        while out and out[-1].strip() in ("", "ready."):
            out = out[:-1]
        return out


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def classify_screen(lines: list[str]) -> str | None:
    """Return 'finished' or 'basic_error' once the program is done, else None.

    The program has started once the autostart 'run' line is visible, or once
    the boot banner ('... bytes free') is gone because the program cleared the
    screen. It is done when BASIC is back at 'ready.' or printed an error.
    """
    stripped = [l.strip() for l in lines]
    run_idx = max((i for i, l in enumerate(stripped) if l == "run"), default=None)
    if run_idx is None:
        if any("bytes free" in l for l in stripped):
            return None
        run_idx = -1
    after = stripped[run_idx + 1:]
    if any(_BASIC_ERROR.match(l) for l in after):
        return "basic_error"
    # Not necessarily the last line: the program may have poked text below the cursor.
    if "ready." in after:
        return "finished"
    return None


def run_prg(
    prg: Path,
    platform: Platform,
    timeout: float = 20.0,
    poll_interval: float = 0.5,
    peeks: list[int] | None = None,
    toolchain: Toolchain | None = None,
) -> RunResult:
    toolchain = toolchain or load_toolchain()
    emulator = toolchain.vice(platform.emulator)
    if not emulator:
        return RunResult("error", detail=f"VICE emulator {platform.emulator} not found")

    port = _free_port()
    cmd = [
        emulator, "-default", "-silent", "+sound", "-warp", "-minimized",
        "-jamaction", "5",
        "-binarymonitor", "-binarymonitoraddress", f"ip4://127.0.0.1:{port}",
        *platform.emulator_args,
        "-autostart", str(prg),
    ]
    started = time.monotonic()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mon = None
    screen: list[str] = []
    try:
        mon = BinaryMonitor(port)
        bank = mon.banks().get("cpu", 0)
        mon.resume()
        end = platform.screen_addr + platform.columns * platform.rows - 1
        while True:
            time.sleep(poll_interval)
            if proc.poll() is not None:
                return RunResult("jam", screen, time.monotonic() - started, "emulator quit (CPU JAM)")
            try:
                data = mon.read_memory(platform.screen_addr, end, bank)
                screen = screen_to_lines(data, platform.columns)
                elapsed = time.monotonic() - started
                status = classify_screen(screen) or ("timeout" if elapsed > timeout else None)
                # Peek while the machine is still paused, so screen and memory match.
                memory = {a: mon.read_memory(a, a, bank)[0] for a in peeks or []} if status else {}
                mon.resume()
            except (MonitorError, OSError):
                if proc.poll() is not None or proc.wait(timeout=2) is not None:
                    return RunResult("jam", screen, time.monotonic() - started, "emulator quit (CPU JAM)")
                raise
            if status:
                detail = "still running at timeout" if status == "timeout" else ""
                return RunResult(status, screen, elapsed, detail, memory)
    except (MonitorError, OSError, subprocess.TimeoutExpired) as exc:
        return RunResult("error", screen, time.monotonic() - started, str(exc))
    finally:
        if mon:
            mon.quit()
            mon.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
