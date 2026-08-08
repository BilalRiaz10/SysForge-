# SysForge — Real-Time Parallel Windows System Utility

**SysForge** is a high-performance, multi-threaded Windows desktop system utility designed for real-time hardware monitoring, process management, and system cleaning. It features a Cyberpunk / Glassmorphism dark interface built with Python (`tkinter`, `psutil`, `concurrent.futures`).

---

## Key Features

### ◈ Tab 1 — Live Hardware Monitor
- **Per-Core CPU Progress Bars**: Real-time per-core CPU usage update every 500 ms.
- **CPU Waveform History**: Smooth double-buffered canvas line graph tracking overall CPU load.
- **Memory Allocation Tracking**: Displays RAM used (in MB and percentage) alongside total installed physical memory.
- **CPU Stress Test**: Integrated 10-second multi-threaded stress test button to launch parallel CPU-bound loops across all logical cores.
- **GPU Display Adapter Detection**: Displays active graphics adapter information.

### ◈ Tab 2 — Process Controller
- **Parallel Process Enumeration**: Uses `ThreadPoolExecutor` worker threads to query running processes concurrently.
- **5-Column Process Table**: Displays Process Name, PID, CPU %, RAM (MB), and Status (`Running`, `Sleeping`, `Stopped`).
- **Search & Sort**: Real-time name filtering and interactive column sorting.
- **Process Management**:
  - **Launch**: Launch executables with browse file picker.
  - **Suspend / Resume**: Pause and resume process execution (`psutil.Process.suspend() / resume()`).
  - **Kill**: Terminate processes with confirmation dialog and **system-critical PID protection** (`PID < 10`, `System`, `csrss.exe`, `smss.exe`, `wininit.exe`, `lsass.exe`).

### ◈ Tab 3 — Parallel System Cleaner
- **High-Speed `os.scandir` Engine**: 7 parallel directory worker threads using native Windows `WIN32_FIND_DATA` caching for ultra-fast recursive scanning.
- **Scan Targets**:
  - `C:\Windows\Temp` & `%TEMP%`
  - `C:\Windows\Prefetch`
  - `C:\Windows\SoftwareDistribution\Download` (Windows Update Cache)
  - Chrome & Edge Browser Caches
  - `C:\$Recycle.Bin`
- **Live Statistics & Summary**: Displays file list with full paths, size formatting (KB/MB), last modified dates (`DD/MM/YYYY`), and category totals.
- **Parallel Deletion**: Delete selected files in parallel with progress bar tracking, safety path checking, and confirmation dialogs.

### ◈ Live Telemetry Proof Panel (`F2`)
- Press <kbd>F2</kbd> anytime to toggle a live overlay panel showing real-time background thread wake timestamps, polling intervals, raw CPU arrays, and scan durations.

---

## Requirements

- **OS**: Windows 10 / 11
- **Python**: Python 3.8 or higher
- **Dependencies**: `psutil`

---

## Installation & Running

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/SysForge.git
   cd SysForge
   ```

2. **Install Dependencies**:
   ```bash
   pip install psutil
   ```

3. **Run Application**:
   ```bash
   python Sys_Forge.py
   ```
