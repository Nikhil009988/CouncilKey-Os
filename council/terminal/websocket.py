"""CouncilKey-Os WebSocket Terminal - Cross-platform terminal for agents."""
from __future__ import annotations

import asyncio
import os
import sys
import signal
import subprocess
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect


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
            # On Unix, use pty
            import pty
            import os
            self.pid, self.master_fd = pty.fork()
            
            if self.pid == 0:
                # Child process
                os.setsid()
                os.environ.update(self.env)
                os.execvpe(self.shell, [self.shell], self.env)
            else:
                # Parent process
                import fcntl
                import termios
                import struct
                # Set window size
                winsize = struct.pack("HHHH", 24, 80, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
        
        self._running = True
    
    def resize(self, rows: int, cols: int) -> None:
        """Resize the terminal."""
        if not self.is_windows and hasattr(self, 'master_fd') and self.master_fd is not None:
            import fcntl
            import termios
            import struct
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
    
    def write(self, data: bytes) -> None:
        """Write to terminal."""
        if self.is_windows:
            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(data)
                    self.process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
        else:
            if hasattr(self, 'master_fd') and self.master_fd is not None:
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
        """Read from PTY on Unix."""
        import os
        loop = asyncio.get_event_loop()
        while self._running and hasattr(self, 'master_fd') and self.master_fd is not None:
            try:
                data = await loop.run_in_executor(None, os.read, self.master_fd, 1024)
                if not data:
                    break
                await ws.send_bytes(data)
            except Exception:
                break
    
    async def _read_loop_windows(self, ws: WebSocket) -> None:
        """Read from subprocess on Windows."""
        loop = asyncio.get_event_loop()
        while self._running and self.process and self.process.stdout:
            try:
                data = await loop.run_in_executor(None, self.process.stdout.read, 1024)
                if not data:
                    break
                await ws.send_bytes(data)
            except Exception:
                break
    
    def close(self) -> None:
        """Close the terminal session."""
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
            if hasattr(self, 'pid') and self.pid is not None:
                try:
                    os.killpg(os.getpgid(self.pid), signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    pass
            if hasattr(self, 'master_fd') and self.master_fd is not None:
                try:
                    os.close(self.master_fd)
                except OSError:
                    pass


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
    session.start()
    
    # Send welcome
    platform = "Windows" if sys.platform == "win32" else "Unix"
    await ws.send_text(f"\r\n\x1b[1;32mCouncilKey-Os Terminal - Agent: {agent} ({platform})\x1b[0m\r\n")
    await ws.send_text(f"Shell: {session.shell}\r\nType 'exit' to close.\r\n\r\n")
    
    # Start read loop
    read_task = asyncio.create_task(session.read_loop(ws))
    
    try:
        while True:
            message = await ws.receive()
            
            if "bytes" in message:
                # Binary input (raw keystrokes)
                session.write(message["bytes"])
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
                    session.write(text.encode())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_text(f"\r\n\x1b[1;31mTerminal error: {e}\x1b[0m\r\n")
    finally:
        session.close()
        read_task.cancel()
        try:
            await read_task
        except asyncio.CancelledError:
            pass