# Single Executable Binary Packaging

**Goal:** Ship a single executable (`setup.exe` / `setup.app`) so users don't need git or Python installed — just double-click.

**Attempted:**

## PyInstaller Method (Standard for Python Single Binary)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name CouncilKey-Os-Setup setup-gui.py
# Creates dist/CouncilKey-Os-Setup (Linux) or dist/CouncilKey-Os-Setup.exe (Windows) single executable binary 100MB+
# --onefile = single executable binary
# --windowed = no console, GUI only (Windows)
# --name CouncilKey-Os-Setup = binary name
# --add-data for smart-initial etc.
```

**Result in Sandbox:**

- Installed PyInstaller 6.21.0 successfully
- Build failed with: `ERROR: Python shared library ('libpython3.11.so.1.0') was not found! If you are using system python on Debian/Ubuntu, you might need to install a separate package by running apt install libpython3.11`
- Tried `sudo apt update` failed `Failed to fetch http://deb.debian.org/debian/dists/bookworm/InRelease Connection failed [IP: 151.101.2.132 80]`
- Tried `sudo apt install libpython3.11 python3-tk` failed `Unable to locate package libpython3.11` and `Package python3-tk has no installation candidate` due to apt update failing no internet to deb.debian.org
- Tried to find libpython3.11.so via `find /usr -name "libpython3*"` found only docs, no .so file
- `python3-config --ldflags` not found, `libpython3.11.a` not found in `/usr/lib/python3.11/config-3.11-x86_64-linux-gnu/` (no such file or directory)
- Sandbox is minimal Debian without python dev packages and no internet to deb.debian.org for apt

**Fallback without a single binary:**

A single binary is 100MB+; the batch fallback is 2KB and downloads Python only if needed:

- `setup-windows-easy.bat` and `setup-windows-easy-final.bat` - Windows batch double-click does everything, downloads Python if needed, no need Python installed, batch file does everything
  - Checks if Python installed via `where python`
  - If not, tries `winget install Python.Python.3.11 --silent` (Windows 10/11 built-in package manager)
  - If winget not found, tries PowerShell `Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile %TEMP%\python-installer.exe` + `%TEMP%\python-installer.exe /quiet InstallAllUsers=0 PrependPath=1`
  - Then runs `setup-easy-one-click.py` or `setup-gui.py`
  - Batch: 2KB + Python installer 24MB (only if needed) vs 100MB+ single binary

- `setup-linux-easy.sh` - Linux shell double-click or bash, checks Python, installs via apt/dnf/pacman if needed, runs GUI

- `setup-gui.py` and `setup-easy-one-click.py` - Single file, no dependencies except Python + tkinter (built-in on Windows, Linux, macOS), auto-downloads repo zip from GitHub if not present (no need git clone), auto-detects USB drives with free space, GUI for USB selection with progress bar

**To Build Single Binary Manually on Real PC (Not Sandbox) with Python Dev:**

On real PC with Python dev and internet:

```bash
# Linux
sudo apt update && sudo apt install -y libpython3.11 python3-tk python3-venv
pip install pyinstaller
pyinstaller --onefile --windowed --name CouncilKey-Os-Setup setup-gui.py
# Output: dist/CouncilKey-Os-Setup (single executable binary, no Python needed, GUI)
# Size: ~50-100MB (includes Python interpreter + tkinter + smart-initial)

# Windows (with Python installed)
pip install pyinstaller
pyinstaller --onefile --windowed --name CouncilKey-Os-Setup.exe --icon=icon.ico setup-gui.py
# Output: dist/CouncilKey-Os-Setup.exe (single executable binary, no Python needed, double-click)
# Size: ~50-100MB

# macOS
pip install pyinstaller
pyinstaller --onefile --windowed --name CouncilKey-Os-Setup --icon=icon.icns setup-gui.py
# Output: dist/CouncilKey-Os-Setup (single binary) or dist/CouncilKey-Os-Setup.app (macOS app bundle)
```

**Time to Build Single Binary:**

- PyInstaller onefile windowed: 5-10 minutes, needs PyInstaller + tkinter + 1GB RAM + libpython3.11.so, creates single executable binary 50-100MB
- In sandbox, failed due to missing libpython3.11.so and no internet to apt, but spec file created: `CouncilKey-Os-Setup.spec` and `setup-binary.spec`
- To build manually on real PC: `pip install pyinstaller && pyinstaller --onefile --windowed --name CouncilKey-Os-Setup setup-gui.py` - 5-10 min

**Without a single binary (recommended):**

- One-liner: `curl -fsSL https://raw.githubusercontent.com/Nikhil009988/CouncilKey-Os/main/install.sh | bash -s -- /mnt/council all` (Bash) and `iwr -useb .../install.ps1 | iex` (PowerShell) - Auto-detects USB, GUI selector, progress bar
- GUI: `python3 setup-gui.py` or `python3 setup-easy-one-click.py` - GUI with auto-detect USB, format options exFAT/F2FS/ext4, progress bar real-time, log real-time
- Batch fallback: double-click `setup-windows-easy.bat` — checks for Python, downloads it via winget/PowerShell if missing, then runs the GUI setup

**Conclusion:**

A single binary (PyInstaller `--onefile`) is possible but was not buildable in this sandbox (no internet to fetch `libpython3.11.so`); the spec files are included for building on a real machine. For most users the one-liner + GUI + batch fallback is simpler than shipping a 50-100MB binary: the batch file is 2KB and downloads Python only if needed.
