"""
Windows mouse/keyboard control via a persistent PowerShell subprocess.
Works from WSL2 — sends real Win32 events to Windows applications.
One PowerShell process is kept alive for the session (no per-call startup cost).
"""

import subprocess
import threading
import time


_INIT_SCRIPT = r"""
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinInput {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, int extra);
    [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int vk);
}
"@ -ErrorAction SilentlyContinue
Write-Host "INIT_OK"
"""


class WinInputBridge:
    """
    Persistent PowerShell bridge for Win32 input events.
    Call start() before use, close() when done.
    """

    LDOWN  = 0x0002
    LUP    = 0x0004
    RDOWN  = 0x0008
    RUP    = 0x0010

    VK_CTRL = 0x11
    VK_C    = 0x43
    KEYUP   = 0x0002   # flag for keybd_event

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._ready = False

    def start(self) -> bool:
        """Launch the PowerShell process and initialise the Win32 type. Returns True on success."""
        try:
            self._proc = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
            )
        except FileNotFoundError:
            return False  # powershell.exe not found (not WSL2 or wrong PATH)

        self._proc.stdin.write(_INIT_SCRIPT + "\n")
        self._proc.stdin.flush()

        # Wait for INIT_OK (up to 5s)
        deadline = time.time() + 5
        while time.time() < deadline:
            line = self._proc.stdout.readline().strip()
            if line == "INIT_OK":
                self._ready = True
                return True
        return False

    def close(self):
        if self._proc:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.kill()
            self._proc = None
        self._ready = False

    # ------------------------------------------------------------------
    # Public input methods
    # ------------------------------------------------------------------

    def move_to(self, x: int, y: int):
        self._run(f"[WinInput]::SetCursorPos({x}, {y})")

    def left_click(self, x: int, y: int):
        self._run(
            f"[WinInput]::SetCursorPos({x},{y});"
            f"Start-Sleep -Milliseconds 40;"
            f"[WinInput]::mouse_event(0x0002,0,0,0,0);"
            f"Start-Sleep -Milliseconds 25;"
            f"[WinInput]::mouse_event(0x0004,0,0,0,0)"
        )

    def right_click(self, x: int, y: int):
        self._run(
            f"[WinInput]::SetCursorPos({x},{y});"
            f"Start-Sleep -Milliseconds 40;"
            f"[WinInput]::mouse_event(0x0008,0,0,0,0);"
            f"Start-Sleep -Milliseconds 25;"
            f"[WinInput]::mouse_event(0x0010,0,0,0,0)"
        )

    def read_clipboard(self) -> str:
        """Return the current Windows clipboard text."""
        return self._run_output("Get-Clipboard")

    def clear_clipboard(self):
        """Set clipboard to a known sentinel so stale POE text is never mistaken for fresh."""
        self._run("Set-Clipboard -Value 'AUTOCRAFT_CLEAR'")

    def ctrl_c(self, x: int, y: int):
        """Move to (x,y) and send Ctrl+Alt+C to copy the hovered POE item with prefix/suffix info."""
        self._run(
            f"[WinInput]::SetCursorPos({x},{y});"
            f"Start-Sleep -Milliseconds 250;"
            f"[WinInput]::keybd_event(0x11,0,0,0);"    # CTRL down
            f"[WinInput]::keybd_event(0x12,0,0,0);"    # ALT down
            f"[WinInput]::keybd_event(0x43,0,0,0);"    # C down
            f"Start-Sleep -Milliseconds 40;"
            f"[WinInput]::keybd_event(0x43,0,2,0);"    # C up
            f"[WinInput]::keybd_event(0x12,0,2,0);"    # ALT up
            f"[WinInput]::keybd_event(0x11,0,2,0)"     # CTRL up
        )

    def is_key_pressed(self, vk_code: int) -> bool:
        """Return True if the given VK key is currently held down (reads raw hardware state)."""
        result = self._run_output(
            f"Write-Host ([WinInput]::GetAsyncKeyState({vk_code}) -band 0x8000)"
        )
        return result.strip() not in ("", "0", "False")


    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self, cmd: str, timeout: float = 3.0):
        """Send one command line and wait for the CMD_DONE sentinel."""
        self._run_output(cmd, timeout)

    def _run_output(self, cmd: str, timeout: float = 3.0) -> str:
        """Send one command line, collect output lines until CMD_DONE, return them."""
        if not self._ready or self._proc is None:
            raise RuntimeError("WinInputBridge not started")
        output = []
        with self._lock:
            self._proc.stdin.write(cmd + "; Write-Host 'CMD_DONE'\n")
            self._proc.stdin.flush()
            deadline = time.time() + timeout
            while time.time() < deadline:
                line = self._proc.stdout.readline().strip()
                if line == "CMD_DONE":
                    return "\n".join(output)
                output.append(line)
        raise TimeoutError(f"PowerShell command timed out: {cmd[:60]}")
