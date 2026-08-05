"""CouncilKey-Os WebSocket Terminal - cross-platform terminal for agents.

Unix:   event-driven PTY via asyncio.add_reader - no blocking executor threads,
        clean cancellation, no fd-close deadlocks.
Windows: subprocess with pipes.

(Previously the Unix path used loop.run_in_executor(os.read, ...) which leaked
a blocked thread per session and could deadlock the whole event loop when the
master fd was closed while the read thread was still blocked.)
"""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from council.terminal.guard import check_command, strip_ansi

if sys.platform == "win32":  # pragma: no cover - Windows-only guards
    fcntl = None
    pty = None
    struct = None
    termios = None
else:
    import fcntl
    import pty
    import struct
    import termios


class TerminalSession:
    """Manages a terminal session (PTY on Unix, subprocess on Windows)."""

    def __init__(self, shell: str | None = None, env: dict | None = None):
        if shell is None:
            shell = "powershell.exe" if sys.platform == "win32" else os.environ.get("SHELL", "/bin/bash")
        self.shell = shell
        self.env = env or os.environ.copy()
        self.process: Optional[subprocess.Popen] = None
        self._running = False
        self.is_windows = sys.platform == "win32"
        self.pid: int | None = None
        self.master_fd: int | None = None

    # ------------------------------------------------------------------ life
    def start(self) -> None:
        """Start the terminal session."""
        self.env["TERM"] = "xterm-256color"
        self.env["COLORTERM"] = "truecolor"

        if self.is_windows:
            # On Windows, use subprocess with pipes
            self.process = subprocess.Popen(
                [self.shell],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=self.env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            master_fd, slave_fd = pty.openpty()
            pid = os.fork()
            if pid == 0:
                # Child: new session, acquire controlling tty, exec shell.
                try:
                    os.setsid()
                    tty_fd = os.open(os.ttyname(slave_fd), os.O_RDWR)
                    os.dup2(tty_fd, 0)
                    os.dup2(tty_fd, 1)
                    os.dup2(tty_fd, 2)
                    if tty_fd > 2:
                        os.close(tty_fd)
                    os.close(slave_fd)
                    os.execvpe(self.shell, [self.shell], self.env)
                except Exception:
                    os._exit(127)
            else:
                os.close(slave_fd)
                self.pid = pid
                self.master_fd = master_fd
                self._set_winsize(24, 80)

        self._running = True

    # ------------------------------------------------------------------ io
    def _set_winsize(self, rows: int, cols: int) -> None:
        if self.master_fd is None:
            return
        try:
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    def resize(self, rows: int, cols: int) -> None:
        if not self.is_windows:
            self._set_winsize(rows, cols)

    def write(self, data: bytes) -> None:
        """Write to terminal."""
        if self.is_windows:
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(data)
                    self.process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
        elif self.master_fd is not None:
            try:
                os.write(self.master_fd, data)
            except OSError:
                pass

    async def read_loop(self, ws: WebSocket) -> None:
        """Read from terminal and send to WebSocket."""
        if self.is_windows:
            await self._read_loop_windows(ws)
        else:
            await self._read_loop_unix(ws)

    async def _read_loop_unix(self, ws: WebSocket) -> None:
        """Event-driven PTY read on Unix (no blocking threads)."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        fd = self.master_fd

        def _on_readable() -> None:
            # Runs on the event loop; must never raise or we starve the loop.
            try:
                if fd is None:
                    return
                data = os.read(fd, 1024)
                if not data:
                    try:
                        loop.remove_reader(fd)
                    except Exception:
                        pass
                    queue.put_nowait(None)  # EOF sentinel
                else:
                    queue.put_nowait(data)
            except OSError:
                try:
                    loop.remove_reader(fd)
                except Exception:
                    pass
                queue.put_nowait(None)
            except Exception:
                try:
                    loop.remove_reader(fd)
                except Exception:
                    pass

        if fd is not None:
            loop.add_reader(fd, _on_readable)
        try:
            while self._running:
                data = await queue.get()
                if data is None:
                    break
                await ws.send_bytes(data)
        finally:
            if fd is not None:
                try:
                    loop.remove_reader(fd)
                except Exception:
                    pass

    async def _read_loop_windows(self, ws: WebSocket) -> None:
        """Read from subprocess on Windows."""
        while self._running and self.process and self.process.stdout:
            data = await asyncio.to_thread(self.process.stdout.read, 1024)
            if not data:
                break
            await ws.send_bytes(data)

    def close(self) -> None:
        """Close the terminal session (safe to call more than once)."""
        self._running = False
        if self.is_windows:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                except Exception:
                    pass
        else:
            if self.pid is not None:
                for sig in (signal.SIGTERM, signal.SIGKILL):
                    try:
                        os.killpg(self.pid, sig)
                    except (ProcessLookupError, OSError):
                        break
                try:
                    os.waitpid(self.pid, os.WNOHANG)  # reap the zombie
                except (ChildProcessError, OSError):
                    pass
                self.pid = None
            if self.master_fd is not None:
                try:
                    os.close(self.master_fd)
                except OSError:
                    pass
                self.master_fd = None


async def terminal_websocket(ws: WebSocket, agent: str = "council") -> None:
    """WebSocket endpoint for terminal (cross-platform)."""
    await ws.accept()

    # Determine shell and env based on agent
    shell = None
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"

    if agent == "hermes":
        env["HERMES_HOME"] = env.get("HERMES_HOME", "/var/lib/council/hermes/real_home")
    elif agent == "openclaw":
        env["OPENCLAW_HOME"] = env.get("OPENCLAW_HOME", "/var/lib/council/openclaw")
    elif agent == "agent-zero":
        env["AGENT_ZERO_HOME"] = env.get("AGENT_ZERO_HOME", "/var/lib/council/agent-zero")

    session = TerminalSession(shell=shell, env=env)
    try:
        session.start()
    except Exception as exc:
        await ws.send_text(f"\r\n\x1b[1;31mTerminal error: {exc}\x1b[0m\r\n")
        await ws.close()
        return

    # Send welcome
    platform = "Windows" if sys.platform == "win32" else "Unix"
    await ws.send_text(f"\r\n\x1b[1;32mCouncilKey-Os Terminal - Agent: {agent} ({platform})\x1b[0m\r\n")
    await ws.send_text(f"Shell: {session.shell}\r\nType 'exit' to close.\r\n\r\n")

    # Start read loop
    read_task = asyncio.create_task(session.read_loop(ws))
    guard_buf = b""  # command-line buffer for the danger guard

    async def _write_guarded(data: bytes) -> None:
        """Write raw bytes, buffering complete lines so the command guard can
        inspect them before they reach the PTY."""
        nonlocal guard_buf
        guard_buf += data
        while True:
            nl = guard_buf.find(b"\n")
            if nl == -1:
                # interactive escape/control sequences flush immediately
                if b"\x1b" in guard_buf or any(
                    b < 32 and b not in (9, 10, 13) for b in guard_buf
                ):
                    session.write(guard_buf)
                    guard_buf = b""
                break
            line = guard_buf[:nl]
            guard_buf = guard_buf[nl + 1:]
            line = line.rstrip(b"\r")
            clean = strip_ansi(line.decode(errors="ignore")).strip()
            if clean:
                allowed, reason = check_command(clean)
                if not allowed:
                    await ws.send_text(
                        f"\r\n\x1b[1;33m[guard] blocked: {reason}. "
                        "Prefix with '!force' to override.\x1b[0m\r\n"
                    )
                    continue
            session.write(line + b"\n")

    try:
        while True:
            message = await ws.receive()

            if "bytes" in message:
                # Binary input (raw keystrokes)
                await _write_guarded(message["bytes"])
            elif "text" in message:
                # Text input (could be resize command)
                text = message["text"]
                if text.startswith("__RESIZE__:"):
                    # Format: __RESIZE__:rows:cols
                    try:
                        _, rows, cols = text.split(":")
                        session.resize(int(rows), int(cols))
                    except Exception:
                        pass
                else:
                    await _write_guarded(text.encode())
    except WebSocketDisconnect:
        pass
    except RuntimeError:
        pass  # client already gone ("Cannot call receive once a disconnect...")
    except Exception as e:
        try:
            await ws.send_text(f"\r\n\x1b[1;31mTerminal error: {e}\x1b[0m\r\n")
        except Exception:
            pass
    finally:
        # Cancel + drain the reader task FIRST so its finally block can
        # unregister the fd watcher, then tear the session down (closing the
        # master fd must not race a registered reader callback).
        read_task.cancel()
        try:
            await read_task
        except asyncio.CancelledError:
            pass
        session.close()
