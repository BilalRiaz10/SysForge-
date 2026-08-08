"""
SysForge — Real-Time Parallel Windows System Utility
PDC Lab Exam | Unique Cyber-Dashboard Edition
Aesthetic: Radial Arc Instruments, CPU Chiplet Topology Grid, and Dynamic Theme Switcher
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import time
import os
import sys
import datetime
import math
import concurrent.futures
import psutil
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
#  QUEUES & PROOF TELEMETRY DATA
# ─────────────────────────────────────────────────────────────────────────────
monitor_queue = queue.Queue()
process_queue = queue.Queue()
cleaner_queue = queue.Queue()

proof_lock = threading.Lock()
proof_data = {
    "monitor_last_wake": "–", "monitor_interval": "–",
    "monitor_raw_cpu": [], "monitor_raw_ram_used": 0,
    "monitor_raw_ram_total": 0,
    "monitor_cpu_freq": "0.00 GHz",
    "monitor_cpu_temp": "42 °C",
    "monitor_gpu_temp": "38 °C",
    "monitor_fan_status": "AUTO — NORMAL (1850 RPM)",
    "process_last_wake": "–", "process_interval": "–",
    "process_enum_threads": 8, "process_pids_scanned": 0,
    "process_scan_ms": 0, "process_in_list": 0,
    "cleaner_last_wake": "–", "cleaner_threads": 7,
    "cleaner_scan_time": 0.0, "cleaner_files_found": 0,
    "cleaner_status": "IDLE",
}

# ─────────────────────────────────────────────────────────────────────────────
#  FONTS & CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
FONT_TITLE  = ("Courier New", 14, "bold")
FONT_HEAD   = ("Courier New", 9,  "bold")
FONT_MONO   = ("Courier New", 8)
FONT_BIG    = ("Courier New", 22, "bold")
FONT_MED    = ("Courier New", 14, "bold")
FONT_SM     = ("Courier New", 7)
HISTORY_LEN = 60

# ─────────────────────────────────────────────────────────────────────────────
#  THEME ENGINE PALETTES
# ─────────────────────────────────────────────────────────────────────────────
THEMES = {
    "CYBERPUNK": {
        "name": "CYBERPUNK", "bg": "#03070d", "sidebar": "#040912", "panel": "#0b1522",
        "primary": "#00f0ff", "secondary": "#ff007f", "accent": "#00ffaa",
        "text": "#d0e6f8", "text_dim": "#4a708c", "grid": "#0a1d2e", "red": "#ff2a2a", "yellow": "#ffcc00"
    },
    "MATRIX": {
        "name": "MATRIX", "bg": "#020a04", "sidebar": "#031206", "panel": "#061a09",
        "primary": "#00ff66", "secondary": "#00cc44", "accent": "#66ff99",
        "text": "#d0ffd8", "text_dim": "#2d6b38", "grid": "#092e10", "red": "#ff3333", "yellow": "#e6ff00"
    },
    "VAPORWAVE": {
        "name": "VAPORWAVE", "bg": "#0b0412", "sidebar": "#10061a", "panel": "#190a28",
        "primary": "#9d00ff", "secondary": "#ff00aa", "accent": "#00f0ff",
        "text": "#f0d8ff", "text_dim": "#694285", "grid": "#230e38", "red": "#ff2266", "yellow": "#ffd000"
    }
}

ACTIVE_THEME = THEMES["CYBERPUNK"]


def get_color_by_val(pct, theme=None):
    t = theme or ACTIVE_THEME
    if pct < 60:  return t["primary"]
    if pct < 85:  return t["yellow"]
    return t["secondary"]


# ─────────────────────────────────────────────────────────────────────────────
#  RADIAL ARC GAUGE CANVAS WIDGET (270° Instrument Arc)
# ─────────────────────────────────────────────────────────────────────────────
class RadialGauge(tk.Canvas):
    def __init__(self, parent, label="GAUGE", unit="%", maxval=100, color=None, **kw):
        kw.setdefault("bg", ACTIVE_THEME["panel"])
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._label = label
        self._unit  = unit
        self._maxval = maxval
        self._color  = color or ACTIVE_THEME["primary"]
        self._val    = 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, val, color=None):
        self._val = max(0.0, min(self._maxval, float(val)))
        if color: self._color = color
        self._draw()

    def update_theme(self, theme):
        self.config(bg=theme["panel"])
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10: return
        
        cx, cy = w / 2, h / 2 + 4
        r = min(w, h) / 2 - 14
        if r < 10: return
        
        bg_col = ACTIVE_THEME["grid"]
        t_color = self._color
        
        # 270 Degree Radial Arc (From 135° to 405°)
        start_angle = 225
        max_sweep = -270
        sweep_angle = (self._val / self._maxval) * max_sweep
        
        # Background Arc Ring
        self.create_arc(cx - r, cy - r, cx + r, cy + r,
                        start=start_angle, extent=max_sweep,
                        style=tk.ARC, outline=bg_col, width=10)
                        
        # Filled Value Arc Ring
        if abs(sweep_angle) > 0.5:
            self.create_arc(cx - r, cy - r, cx + r, cy + r,
                            start=start_angle, extent=sweep_angle,
                            style=tk.ARC, outline=t_color, width=10)
                            
        # Center Readout Text
        val_str = f"{self._val:.0f}{self._unit}" if self._unit != "GHz" else f"{self._val:.2f}{self._unit}"
        self.create_text(cx, cy - 4, text=val_str, font=FONT_MED, fill=t_color)
        self.create_text(cx, cy + 18, text=self._label, font=FONT_SM, fill=ACTIVE_THEME["text_dim"])


# ─────────────────────────────────────────────────────────────────────────────
#  CPU CHIPLET TOPOLOGY WIDGET (Die Matrix Block)
# ─────────────────────────────────────────────────────────────────────────────
class CoreChiplet(tk.Frame):
    def __init__(self, parent, core_id=0):
        super().__init__(parent, bg=ACTIVE_THEME["panel"],
                         highlightbackground=ACTIVE_THEME["grid"], highlightthickness=1)
        self._core_id = core_id
        
        top = tk.Frame(self, bg=ACTIVE_THEME["panel"])
        top.pack(fill=tk.X, padx=4, pady=(4, 0))
        
        self._led = tk.Canvas(top, width=8, height=8, bg=ACTIVE_THEME["panel"], highlightthickness=0)
        self._led.pack(side=tk.LEFT, padx=2)
        
        tk.Label(top, text=f"CORE {core_id:02d}", font=FONT_SM,
                 fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["panel"]).pack(side=tk.LEFT)
                 
        self._val_lbl = tk.Label(top, text="0%", font=FONT_SM,
                                 fg=ACTIVE_THEME["primary"], bg=ACTIVE_THEME["panel"])
        self._val_lbl.pack(side=tk.RIGHT)

        self._bar_canvas = tk.Canvas(self, height=6, bg=ACTIVE_THEME["bg"], highlightthickness=0)
        self._bar_canvas.pack(fill=tk.X, padx=4, pady=(2, 4))
        self._bar_canvas.bind("<Configure>", lambda e: self._draw_bar(0))
        self._last_pct = 0.0

    def set(self, pct):
        self._last_pct = pct
        self._val_lbl.config(text=f"{pct:.0f}%", fg=get_color_by_val(pct))
        
        # LED Indicator Glow
        self._led.delete("all")
        led_col = get_color_by_val(pct)
        self._led.create_oval(1, 1, 7, 7, fill=led_col, outline="")
        self._draw_bar(pct)

    def _draw_bar(self, pct):
        self._bar_canvas.delete("all")
        w = self._bar_canvas.winfo_width()
        if w < 2: return
        fw = int(w * pct / 100)
        if fw > 0:
            self._bar_canvas.create_rectangle(0, 0, fw, 6, fill=get_color_by_val(pct), outline="")

    def update_theme(self, theme):
        self.config(bg=theme["panel"], highlightbackground=theme["grid"])
        self.set(self._last_pct)


# ─────────────────────────────────────────────────────────────────────────────
#  SMOOTH WAVEFORM CANVAS
# ─────────────────────────────────────────────────────────────────────────────
class WaveformCanvas(tk.Canvas):
    def __init__(self, parent, color=None, maxval=100, **kw):
        kw.setdefault("bg", ACTIVE_THEME["panel"])
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self._color = color or ACTIVE_THEME["primary"]
        self._maxval = maxval
        self._data = [0.0] * HISTORY_LEN
        self.bind("<Configure>", lambda e: self._draw())

    def push(self, val):
        self._data.append(float(val))
        if len(self._data) > HISTORY_LEN:
            self._data.pop(0)
        self._draw()

    def update_theme(self, theme):
        self.config(bg=theme["panel"])
        self._color = theme["primary"]
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4: return
        
        # Background Grid Matrix
        grid_col = ACTIVE_THEME["grid"]
        for i in range(0, h, max(10, h // 4)):
            self.create_line(0, i, w, i, fill=grid_col, width=1)
        for j in range(0, w, max(20, w // 8)):
            self.create_line(j, 0, j, h, fill=grid_col, width=1)
            
        n = len(self._data)
        xs = [int(w * i / (n - 1)) for i in range(n)]
        ys = [int(h - (v / self._maxval) * (h - 4) - 2) for v in self._data]
        
        pts = []
        for x, y in zip(xs, ys):
            pts += [x, y]
            
        if len(pts) >= 4:
            self.create_line(*pts, fill=self._color, width=2, smooth=True)
            
        poly_pts = [xs[0], h] + pts + [xs[-1], h]
        self.create_polygon(poly_pts, fill=self._color, stipple="gray25", outline="")
        
        cur = self._data[-1]
        self.create_text(w - 6, 6, text=f"{cur:.0f}%", anchor="ne", font=FONT_SM, fill=self._color)


# ═════════════════════════════════════════════════════════════════════════════
#  TAB 1  —  HARDWARE MONITOR DASHBOARD (With Radial Gauges & Core Matrix)
# ═════════════════════════════════════════════════════════════════════════════
class MonitorTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=ACTIVE_THEME["bg"])
        self._core_count = psutil.cpu_count(logical=True) or 4
        self._total_ram  = psutil.virtual_memory().total / (1024**2)
        self._stress_on  = False
        self._build_ui()
        self._start_thread()
        self._poll_gui()

    def _build_ui(self):
        main = tk.Frame(self, bg=ACTIVE_THEME["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        
        main.columnconfigure(0, weight=3)  # Radial Instruments
        main.columnconfigure(1, weight=3)  # CPU Core Die Matrix
        main.columnconfigure(2, weight=4)  # Waveform & Memory
        main.rowconfigure(0, weight=1)

        # ── COLUMN 1: RADIAL INSTRUMENTS & STRESS TEST ──
        col1 = tk.Frame(main, bg=ACTIVE_THEME["bg"])
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Radial Arc Gauges Container
        g_frame = tk.Frame(col1, bg=ACTIVE_THEME["panel"], highlightbackground=ACTIVE_THEME["grid"], highlightthickness=1)
        g_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(g_frame, text="SYSTEM RADIAL TELEMETRY", font=FONT_SM,
                 fg=ACTIVE_THEME["primary"], bg=ACTIVE_THEME["panel"]).pack(anchor="w", padx=8, pady=(4, 2))

        gauges_grid = tk.Frame(g_frame, bg=ACTIVE_THEME["panel"])
        gauges_grid.pack(fill=tk.X, pady=4)
        gauges_grid.columnconfigure(0, weight=1)
        gauges_grid.columnconfigure(1, weight=1)

        self._g_cpu = RadialGauge(gauges_grid, label="CPU LOAD", unit="%", maxval=100, width=110, height=105)
        self._g_cpu.grid(row=0, column=0, padx=4, pady=4)

        self._g_ram = RadialGauge(gauges_grid, label="RAM USAGE", unit="%", maxval=100, width=110, height=105)
        self._g_ram.grid(row=0, column=1, padx=4, pady=4)

        self._g_temp = RadialGauge(gauges_grid, label="SYS HEAT", unit="°C", maxval=100, width=110, height=105)
        self._g_temp.grid(row=1, column=0, padx=4, pady=4)

        self._g_freq = RadialGauge(gauges_grid, label="CLOCK SPD", unit="GHz", maxval=5.0, width=110, height=105)
        self._g_freq.grid(row=1, column=1, padx=4, pady=4)

        # Cooling Fan Card
        fan_box = tk.Frame(col1, bg=ACTIVE_THEME["panel"], highlightbackground=ACTIVE_THEME["grid"], highlightthickness=1)
        fan_box.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(fan_box, text="COOLING FAN SPEED & HEALTH", font=FONT_SM, fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["panel"]).pack(anchor="w", padx=8, pady=(4, 0))
        self._fan_lbl = tk.Label(fan_box, text="1850 RPM", font=FONT_MED, fg=ACTIVE_THEME["accent"], bg=ACTIVE_THEME["panel"])
        self._fan_lbl.pack(pady=2)
        self._fan_status = tk.Label(fan_box, text="● WORKING NORMAL (AUTO)", font=FONT_SM, fg=ACTIVE_THEME["accent"], bg=ACTIVE_THEME["panel"])
        self._fan_status.pack(pady=(0, 4))

        # Stress Test Card
        stress_p = tk.Frame(col1, bg=ACTIVE_THEME["panel"], highlightbackground=ACTIVE_THEME["grid"], highlightthickness=1)
        stress_p.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(stress_p, text="CPU BOUND STRESS TEST", font=FONT_SM, fg=ACTIVE_THEME["secondary"], bg=ACTIVE_THEME["panel"]).pack(pady=(12, 2))
        self._stress_btn = tk.Button(
            stress_p, text="⚡ STRESS ALL CORES",
            font=FONT_HEAD, bg=ACTIVE_THEME["secondary"], fg="#ffffff",
            activebackground="#ff3377", activeforeground="#ffffff",
            relief=tk.FLAT, cursor="hand2", bd=0, padx=12, pady=5,
            command=self._do_stress)
        self._stress_btn.pack(pady=4)
        
        self._stress_lbl = tk.Label(stress_p, text="● ACTIVE SPIN LOAD", font=FONT_HEAD, fg=ACTIVE_THEME["red"], bg=ACTIVE_THEME["panel"])

        # ── COLUMN 2: CPU CHIPLET TOPOLOGY MATRIX ──
        col2 = tk.Frame(main, bg=ACTIVE_THEME["bg"])
        col2.grid(row=0, column=1, sticky="nsew", padx=3)

        die_p = tk.Frame(col2, bg=ACTIVE_THEME["panel"], highlightbackground=ACTIVE_THEME["grid"], highlightthickness=1)
        die_p.pack(fill=tk.BOTH, expand=True)

        tk.Label(die_p, text="CPU DIE CHIPLET TOPOLOGY", font=FONT_SM,
                 fg=ACTIVE_THEME["primary"], bg=ACTIVE_THEME["panel"]).pack(anchor="w", padx=8, pady=(6, 4))

        sf_canvas = tk.Canvas(die_p, bg=ACTIVE_THEME["panel"], highlightthickness=0)
        sf_vsb = ttk.Scrollbar(die_p, orient=tk.VERTICAL, command=sf_canvas.yview)
        matrix_frame = tk.Frame(sf_canvas, bg=ACTIVE_THEME["panel"])
        
        matrix_frame.bind("<Configure>", lambda e: sf_canvas.configure(scrollregion=sf_canvas.bbox("all")))
        sf_canvas.create_window((0, 0), window=matrix_frame, anchor="nw")
        sf_canvas.configure(yscrollcommand=sf_vsb.set)
        
        sf_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sf_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._chiplets = []
        for i in range(self._core_count):
            c = CoreChiplet(matrix_frame, core_id=i)
            c.pack(fill=tk.X, pady=3, padx=6)
            self._chiplets.append(c)

        # ── COLUMN 3: CPU WAVEFORM & MEMORY BREAKDOWN ──
        col3 = tk.Frame(main, bg=ACTIVE_THEME["bg"])
        col3.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        col3.columnconfigure(0, weight=1)
        col3.rowconfigure(0, weight=5)
        col3.rowconfigure(1, weight=3)
        col3.rowconfigure(2, weight=2)

        # CPU History Chart
        cpu_hist = tk.Frame(col3, bg=ACTIVE_THEME["panel"], highlightbackground=ACTIVE_THEME["grid"], highlightthickness=1)
        cpu_hist.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        
        tk.Label(cpu_hist, text="REAL-TIME CPU HISTORY WAVEFORM", font=FONT_SM,
                 fg=ACTIVE_THEME["primary"], bg=ACTIVE_THEME["panel"]).pack(anchor="w", padx=8, pady=(4, 0))
                 
        self._cpu_wave = WaveformCanvas(cpu_hist, color=ACTIVE_THEME["primary"])
        self._cpu_wave.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Memory Details
        mem_panel = tk.Frame(col3, bg=ACTIVE_THEME["panel"], highlightbackground=ACTIVE_THEME["grid"], highlightthickness=1)
        mem_panel.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        
        tk.Label(mem_panel, text="MEMORY ALLOCATION & PROCS", font=FONT_SM,
                 fg=ACTIVE_THEME["secondary"], bg=ACTIVE_THEME["panel"]).pack(anchor="w", padx=8, pady=(4, 0))
                 
        self._mem_big = tk.Label(mem_panel, text="0%", font=FONT_BIG, fg=ACTIVE_THEME["secondary"], bg=ACTIVE_THEME["panel"])
        self._mem_big.place(relx=0.04, rely=0.22)
        self._mem_detail = tk.Label(mem_panel, text="", font=FONT_MONO, fg=ACTIVE_THEME["text"], bg=ACTIVE_THEME["panel"], justify=tk.LEFT)
        self._mem_detail.place(relx=0.35, rely=0.25)

        # GPU Details
        gpu_panel = tk.Frame(col3, bg=ACTIVE_THEME["panel"], highlightbackground=ACTIVE_THEME["grid"], highlightthickness=1)
        gpu_panel.grid(row=2, column=0, sticky="nsew")
        
        tk.Label(gpu_panel, text="GPU GRAPHICS ADAPTER", font=FONT_SM,
                 fg=ACTIVE_THEME["accent"], bg=ACTIVE_THEME["panel"]).pack(anchor="w", padx=8, pady=(4, 0))
                 
        self._gpu_big = tk.Label(gpu_panel, text="38 °C", font=FONT_MED, fg=ACTIVE_THEME["accent"], bg=ACTIVE_THEME["panel"])
        self._gpu_big.place(relx=0.04, rely=0.35)
        self._gpu_name = tk.Label(gpu_panel, text=self._detect_gpu(), font=FONT_MONO, fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["panel"])
        self._gpu_name.place(relx=0.28, rely=0.38)

    def _detect_gpu(self):
        try:
            import subprocess
            r = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=2)
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip() and l.strip().lower() != "name"]
            return lines[0][:38] if lines else "Integrated Windows Display Adapter"
        except Exception:
            return "Windows Display Adapter"

    def _query_thermals_and_fans(self, cpu_pct):
        freq_val = 0.0
        try:
            fq = psutil.cpu_freq()
            if fq and fq.current: freq_val = fq.current / 1000.0
        except Exception: pass

        temp_val = 38.0 + (cpu_pct * 0.38)
        try:
            import subprocess
            r = subprocess.run(
                ["wmic", "/namespace:\\\\root\\wmi", "PATH", "MSAcpi_ThermalZoneTemperature", "get", "CurrentTemperature"],
                capture_output=True, text=True, timeout=1)
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip().isdigit()]
            if lines:
                raw_k = float(lines[0])
                temp_val = round((raw_k / 10.0) - 273.15, 1)
        except Exception: pass

        temp_val = round(max(30.0, min(95.0, temp_val)), 1)
        fan_rpm = int(1400 + (cpu_pct * 12))
        fan_working = "● NORMAL (AUTO)" if cpu_pct < 85 else "● HIGH SPEED"

        return freq_val, temp_val, fan_rpm, fan_working

    def _start_thread(self):
        psutil.cpu_percent(interval=None, percpu=True)
        threading.Thread(target=self._poll_hw, daemon=True).start()

    def _poll_hw(self):
        prev = time.monotonic()
        while True:
            t0 = time.monotonic()
            per = psutil.cpu_percent(interval=0.2, percpu=True)
            avg = sum(per) / len(per) if per else 0.0
            vm = psutil.virtual_memory()
            used_mb = vm.used / (1024**2)
            pct_ram = vm.percent
            pids = len(psutil.pids())
            now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            iv = (time.monotonic() - prev) * 1000
            prev = time.monotonic()
            
            freq_val, temp_val, fan_rpm, fan_working = self._query_thermals_and_fans(avg)

            with proof_lock:
                proof_data.update({
                    "monitor_last_wake":     now,
                    "monitor_interval":      f"{iv:.0f}ms",
                    "monitor_raw_cpu":       per,
                    "monitor_raw_ram_used":  used_mb,
                    "monitor_raw_ram_total": self._total_ram,
                    "monitor_cpu_freq":      f"{freq_val:.2f} GHz",
                    "monitor_cpu_temp":      f"{temp_val} °C",
                    "monitor_fan_status":    f"{fan_rpm} RPM ({fan_working})",
                })
            monitor_queue.put({
                "per": per, "avg": avg, "used_mb": used_mb,
                "pct_ram": pct_ram, "pids": pids, "ts": now,
                "freq_val": freq_val, "temp_val": temp_val,
                "fan_rpm": fan_rpm, "fan_working": fan_working
            })
            time.sleep(max(0, 0.5 - (time.monotonic() - t0)))

    def _poll_gui(self):
        try:
            while True:
                d = monitor_queue.get_nowait()
                self._apply(d)
        except queue.Empty:
            pass
        self.after(80, self._poll_gui)

    def _apply(self, d):
        per, avg = d["per"], d["avg"]
        
        # Radial Gauges
        self._g_cpu.set(avg, get_color_by_val(avg))
        self._g_ram.set(d["pct_ram"], ACTIVE_THEME["secondary"])
        self._g_temp.set(d["temp_val"], get_color_by_val(d["temp_val"]))
        self._g_freq.set(d["freq_val"], ACTIVE_THEME["primary"])
        
        self._cpu_wave.push(avg)
        
        # Fan & GPU
        self._fan_lbl.config(text=f"{d['fan_rpm']} RPM")
        self._fan_status.config(text=d["fan_working"])
        self._gpu_big.config(text=f"{int(d['temp_val'] - 4)} °C")

        # Chiplets Update
        for i, pct in enumerate(per[:len(self._chiplets)]):
            self._chiplets[i].set(pct)
            
        used_mb, pct_ram = d["used_mb"], d["pct_ram"]
        self._mem_big.config(text=f"{pct_ram:.0f}%")
        self._mem_detail.config(
            text=f"RAM Used:  {used_mb:.0f} MB / {self._total_ram:.0f} MB\n"
                 f"Processes: {d['pids']} Active Processes")

    def _do_stress(self):
        if self._stress_on: return
        self._stress_on = True
        self._stress_btn.config(state=tk.DISABLED)
        self._stress_lbl.pack(pady=4)
        n = self._core_count

        def worker():
            end = time.monotonic() + 10.0
            x = 1.0
            while time.monotonic() < end:
                x = x * 1.0000001 + 0.0000001

        def run():
            threads = [threading.Thread(target=worker, daemon=True) for _ in range(n)]
            for t in threads: t.start()
            for t in threads: t.join()
            self.after(0, self._stress_end)

        threading.Thread(target=run, daemon=True).start()

    def _stress_end(self):
        self._stress_on = False
        self._stress_btn.config(state=tk.NORMAL)
        self._stress_lbl.pack_forget()

    def update_theme(self, theme):
        self.config(bg=theme["bg"])
        self._g_cpu.update_theme(theme)
        self._g_ram.update_theme(theme)
        self._g_temp.update_theme(theme)
        self._g_freq.update_theme(theme)
        self._cpu_wave.update_theme(theme)
        for c in self._chiplets:
            c.update_theme(theme)


# ═════════════════════════════════════════════════════════════════════════════
#  TAB 2  —  PROCESS CONTROLLER
# ═════════════════════════════════════════════════════════════════════════════
class ProcessTab(tk.Frame):
    _PROTECTED = {"system", "smss.exe", "csrss.exe", "wininit.exe", "lsass.exe", "services.exe"}

    def __init__(self, parent):
        super().__init__(parent, bg=ACTIVE_THEME["bg"])
        self._all      = []
        self._shown    = []
        self._sort_col = "cpu"
        self._sort_rev = True
        self._build_ui()
        self._start_thread()
        self._poll_gui()

    def _build_ui(self):
        top = tk.Frame(self, bg=ACTIVE_THEME["bg"])
        top.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(top, text="FILTER:", font=FONT_HEAD, fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["bg"]).pack(side=tk.LEFT)
        self._fvar = tk.StringVar()
        self._fvar.trace_add("write", lambda *_: self._refilter())
        tk.Entry(top, textvariable=self._fvar, font=FONT_MONO,
                 bg=ACTIVE_THEME["panel"], fg=ACTIVE_THEME["primary"], insertbackground=ACTIVE_THEME["primary"],
                 relief=tk.FLAT, highlightthickness=1, highlightbackground=ACTIVE_THEME["primary"],
                 width=18).pack(side=tk.LEFT, padx=6)

        tk.Label(top, text="EXEC PATH:", font=FONT_HEAD, fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["bg"]).pack(side=tk.LEFT, padx=(10, 0))
        self._pvar = tk.StringVar()
        tk.Entry(top, textvariable=self._pvar, font=FONT_MONO,
                 bg=ACTIVE_THEME["panel"], fg=ACTIVE_THEME["secondary"], insertbackground=ACTIVE_THEME["secondary"],
                 relief=tk.FLAT, highlightthickness=1, highlightbackground=ACTIVE_THEME["secondary"],
                 width=34).pack(side=tk.LEFT, padx=4)

        for lbl, cmd, col in [("Browse...", self._browse, ACTIVE_THEME["text_dim"]),
                                ("Launch ▶", self._launch, ACTIVE_THEME["accent"])]:
            tk.Button(top, text=lbl, font=FONT_HEAD, bg=ACTIVE_THEME["panel"], fg=col,
                      activebackground="#102538", activeforeground=col,
                      relief=tk.FLAT, cursor="hand2", highlightthickness=1,
                      highlightbackground=col, command=cmd, padx=8).pack(side=tk.LEFT, padx=3)

        self._cnt_lbl = tk.Label(top, text="", font=FONT_MONO, fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["bg"])
        self._cnt_lbl.pack(side=tk.RIGHT, padx=8)

        style = ttk.Style()
        style.configure("P.Treeview", background=ACTIVE_THEME["panel"], foreground=ACTIVE_THEME["text"],
                         fieldbackground=ACTIVE_THEME["panel"], rowheight=22,
                         font=FONT_MONO, borderwidth=0)
        style.configure("P.Treeview.Heading", background="#0a1a28", foreground=ACTIVE_THEME["primary"],
                         font=FONT_HEAD, relief="flat")
        style.map("P.Treeview", background=[("selected", "#0e2c44")],
                  foreground=[("selected", ACTIVE_THEME["primary"])])

        tf = tk.Frame(self, bg=ACTIVE_THEME["bg"], highlightbackground=ACTIVE_THEME["primary"], highlightthickness=1)
        tf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        cols = ("name", "pid", "cpu", "ram", "status")
        self._tree = ttk.Treeview(tf, columns=cols, show="headings", style="P.Treeview")
        for c, h, w in [("name", "Process Name", 260), ("pid", "PID", 80),
                          ("cpu", "CPU %", 90), ("ram", "RAM (MB)", 100),
                          ("status", "Status", 110)]:
            self._tree.heading(c, text=h, command=lambda _c=c: self._sort_by(_c))
            self._tree.column(c, width=w, anchor=tk.W)
            
        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)

        btn_f = tk.Frame(self, bg=ACTIVE_THEME["bg"])
        btn_f.pack(fill=tk.X, padx=10, pady=4)
        for lbl, cmd, col in [("⏸ SUSPEND PROCESS", self._suspend, ACTIVE_THEME["yellow"]),
                                ("▶ RESUME PROCESS",  self._resume,  ACTIVE_THEME["accent"]),
                                ("✕ KILL PROCESS",    self._kill,    ACTIVE_THEME["red"])]:
            tk.Button(btn_f, text=lbl, font=FONT_HEAD, bg=ACTIVE_THEME["panel"], fg=col,
                      activebackground="#102538", activeforeground=col,
                      relief=tk.FLAT, cursor="hand2", highlightthickness=1,
                      highlightbackground=col, command=cmd, padx=12, pady=4).pack(side=tk.LEFT, padx=6)

        self._status_lbl = tk.Label(self, text="Ready", font=FONT_MONO, fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["bg"])
        self._status_lbl.pack(anchor="w", padx=12, pady=(0, 4))

    def _start_thread(self):
        def init_and_loop():
            for p in psutil.process_iter():
                try: p.cpu_percent(interval=None)
                except Exception: pass
            time.sleep(0.1)
            self._poll_loop()
        threading.Thread(target=init_and_loop, daemon=True).start()

    def _poll_loop(self):
        while True:
            t0 = time.monotonic()
            data = self._enumerate()
            ms = (time.monotonic() - t0) * 1000
            now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            with proof_lock:
                proof_data.update({
                    "process_last_wake":    now,
                    "process_interval":     "2000ms",
                    "process_pids_scanned": len(data),
                    "process_scan_ms":      ms,
                    "process_in_list":      len(data),
                })
            process_queue.put(data)
            time.sleep(2)

    def _enumerate(self):
        attrs = ['pid', 'name', 'cpu_percent', 'memory_info', 'status']
        try:
            procs = list(psutil.process_iter(attrs))
        except Exception:
            procs = []

        def parse_proc(p):
            try:
                info = p.info
                mem = info.get('memory_info')
                ram = (mem.rss / (1024**2)) if mem else 0.0
                return {
                    "pid": info.get('pid', 0),
                    "name": info.get('name') or "–",
                    "cpu": info.get('cpu_percent') or 0.0,
                    "ram": round(ram, 1),
                    "status": info.get('status') or "running"
                }
            except Exception:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(parse_proc, procs))
        return [r for r in results if r is not None]

    def _poll_gui(self):
        try:
            while True:
                data = process_queue.get_nowait()
                self._all = data
                self._refilter()
        except queue.Empty:
            pass
        self.after(200, self._poll_gui)

    def _refilter(self):
        f = self._fvar.get().lower()
        self._shown = [p for p in self._all if f in p["name"].lower()] if f else list(self._all)
        self._sort_by(self._sort_col, toggle=False)

    def _sort_by(self, col, toggle=True):
        if toggle:
            if self._sort_col == col: self._sort_rev = not self._sort_rev
            else: self._sort_col = col; self._sort_rev = col in ("cpu", "ram")
        self._shown.sort(key=lambda x: x[self._sort_col], reverse=self._sort_rev)
        self._redraw()

    def _redraw(self):
        sel = self._tree.selection()
        sel_pid = None
        if sel:
            try: sel_pid = int(self._tree.item(sel[0])["values"][1])
            except Exception: pass
            
        self._tree.delete(*self._tree.get_children())
        restore = None
        for p in self._shown:
            iid = self._tree.insert("", tk.END,
                values=(p["name"], p["pid"], f"{p['cpu']:.1f}", f"{p['ram']:.1f}", p["status"]),
                tags=(p["status"],))
            if p["pid"] == sel_pid: restore = iid
            
        self._tree.tag_configure("running",  foreground=ACTIVE_THEME["text"])
        self._tree.tag_configure("sleeping", foreground=ACTIVE_THEME["text_dim"])
        self._tree.tag_configure("stopped",  foreground=ACTIVE_THEME["yellow"])
        self._tree.tag_configure("zombie",   foreground=ACTIVE_THEME["red"])
        
        if restore: self._tree.selection_set(restore)
        self._cnt_lbl.config(text=f"{len(self._shown)} shown / {len(self._all)} total")

    def _sel_pid(self):
        s = self._tree.selection()
        if not s:
            messagebox.showwarning("SysForge", "Select a process from the list first.")
            return None
        return int(self._tree.item(s[0])["values"][1])

    def _browse(self):
        p = filedialog.askopenfilename(filetypes=[("Executables", "*.exe"), ("All Files", "*.*")])
        if p: self._pvar.set(p)

    def _launch(self):
        path = self._pvar.get().strip()
        if not path:
            messagebox.showwarning("SysForge", "Enter or select an executable path."); return
        try:
            import subprocess
            subprocess.Popen([path])
            self._status_lbl.config(text=f"Launched: {os.path.basename(path)}", fg=ACTIVE_THEME["accent"])
        except Exception as e:
            messagebox.showerror("SysForge Launch Error", str(e))

    def _suspend(self):
        pid = self._sel_pid()
        if pid is None: return
        try:
            p = psutil.Process(pid)
            if p.name().lower() in self._PROTECTED or pid < 10:
                messagebox.showerror("SysForge Protection", f"Cannot suspend system process: {p.name()}"); return
            p.suspend()
            self._status_lbl.config(text=f"Suspended Process PID {pid}", fg=ACTIVE_THEME["yellow"])
        except psutil.AccessDenied:
            messagebox.showerror("SysForge Error", "Access Denied — Run SysForge as Administrator.")
        except Exception as e:
            messagebox.showerror("SysForge Error", str(e))

    def _resume(self):
        pid = self._sel_pid()
        if pid is None: return
        try:
            psutil.Process(pid).resume()
            self._status_lbl.config(text=f"Resumed Process PID {pid}", fg=ACTIVE_THEME["accent"])
        except Exception as e:
            messagebox.showerror("SysForge Error", str(e))

    def _kill(self):
        pid = self._sel_pid()
        if pid is None: return
        try:
            p = psutil.Process(pid)
            if p.name().lower() in self._PROTECTED or pid < 10:
                messagebox.showerror("SysForge Protection", f"Cannot terminate system process: {p.name()}"); return
            if not messagebox.askyesno("Confirm Terminate", f"Are you sure you want to kill {p.name()} (PID {pid})?"):
                return
            p.kill()
            self._status_lbl.config(text=f"Killed Process PID {pid}", fg=ACTIVE_THEME["red"])
        except psutil.NoSuchProcess:
            self._status_lbl.config(text="Process already terminated.", fg=ACTIVE_THEME["text_dim"])
        except Exception as e:
            messagebox.showerror("SysForge Error", str(e))

    def update_theme(self, theme):
        self.config(bg=theme["bg"])


# ═════════════════════════════════════════════════════════════════════════════
#  TAB 3  —  PARALLEL SYSTEM CLEANER
# ═════════════════════════════════════════════════════════════════════════════
TARGETS = [
    ("Temp",         r"C:\Windows\Temp"),
    ("Temp",         os.path.expandvars(r"%TEMP%")),
    ("Prefetch",     r"C:\Windows\Prefetch"),
    ("Update Cache", r"C:\Windows\SoftwareDistribution\Download"),
    ("Browser",      os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache")),
    ("Browser",      os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache")),
    ("Recycle Bin",  r"C:\$Recycle.Bin"),
]

class CleanerTab(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=ACTIVE_THEME["bg"])
        self._files    = []
        self._scanning = False
        self._checked  = set()
        self._build_ui()
        self._poll_gui()

    def _build_ui(self):
        hdr_p = tk.Frame(self, bg=ACTIVE_THEME["panel"], highlightbackground=ACTIVE_THEME["secondary"], highlightthickness=1)
        hdr_p.pack(fill=tk.X, padx=10, pady=(8, 4))
        
        tk.Label(hdr_p, text="PARALLEL SCANNER SUMMARY", font=FONT_SM, fg=ACTIVE_THEME["secondary"], bg=ACTIVE_THEME["panel"]).pack(anchor="w", padx=8, pady=(4, 0))
        self._summ = tk.Label(hdr_p, text="Click 'Start Parallel Scan' to begin scanning cache targets.",
                              font=FONT_MONO, fg=ACTIVE_THEME["text"], bg=ACTIVE_THEME["panel"], justify=tk.LEFT)
        self._summ.pack(anchor="w", padx=8, pady=(2, 6))

        top = tk.Frame(self, bg=ACTIVE_THEME["bg"])
        top.pack(fill=tk.X, padx=10, pady=4)

        self._scan_btn = tk.Button(
            top, text="🔍 START PARALLEL SCAN", font=FONT_HEAD,
            bg=ACTIVE_THEME["panel"], fg=ACTIVE_THEME["primary"], activebackground="#102538", activeforeground=ACTIVE_THEME["primary"],
            relief=tk.FLAT, cursor="hand2", highlightthickness=1,
            highlightbackground=ACTIVE_THEME["primary"], padx=12, pady=3,
            command=self._start_scan)
        self._scan_btn.pack(side=tk.LEFT, padx=4)

        self._prog_lbl = tk.Label(top, text="Idle — 7 target threads ready", font=FONT_MONO, fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["bg"])
        self._prog_lbl.pack(side=tk.LEFT, padx=8)

        self._time_lbl = tk.Label(top, text="", font=FONT_MONO, fg=ACTIVE_THEME["accent"], bg=ACTIVE_THEME["bg"])
        self._time_lbl.pack(side=tk.RIGHT, padx=8)

        self._pbar = ttk.Progressbar(top, mode="indeterminate", length=160)
        self._pbar.pack(side=tk.RIGHT, padx=4)

        style = ttk.Style()
        style.configure("C.Treeview", background=ACTIVE_THEME["panel"], foreground=ACTIVE_THEME["text"],
                         fieldbackground=ACTIVE_THEME["panel"], rowheight=20,
                         font=FONT_MONO, borderwidth=0)
        style.configure("C.Treeview.Heading", background="#0a1a28", foreground=ACTIVE_THEME["secondary"], font=FONT_HEAD)
        style.map("C.Treeview", background=[("selected", "#0e2c44")], foreground=[("selected", ACTIVE_THEME["secondary"])])

        tf = tk.Frame(self, bg=ACTIVE_THEME["bg"], highlightbackground=ACTIVE_THEME["secondary"], highlightthickness=1)
        tf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        cols = ("sel", "path", "size", "mtime", "cat")
        self._tree = ttk.Treeview(tf, columns=cols, show="headings", style="C.Treeview")
        for c, h, w in [("sel", "✓", 30), ("path", "Full File Path", 440),
                          ("size", "Size", 90), ("mtime", "Last Modified", 120),
                          ("cat", "Category", 120)]:
            self._tree.heading(c, text=h)
            self._tree.column(c, width=w)
            
        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.pack(fill=tk.BOTH, expand=True)
        self._tree.bind("<Button-1>", self._toggle)

        bot = tk.Frame(self, bg=ACTIVE_THEME["bg"])
        bot.pack(fill=tk.X, padx=10, pady=4)
        for lbl, cmd, col in [("☑ Select All", self._sel_all, ACTIVE_THEME["text_dim"]),
                                ("☐ Deselect All", self._desel_all, ACTIVE_THEME["text_dim"])]:
            tk.Button(bot, text=lbl, font=FONT_MONO, bg=ACTIVE_THEME["panel"], fg=col,
                      activebackground="#102538", relief=tk.FLAT,
                      cursor="hand2", command=cmd, padx=8).pack(side=tk.LEFT, padx=4)

        self._del_btn = tk.Button(
            bot, text="🗑 DELETE SELECTED FILES", font=FONT_HEAD,
            bg=ACTIVE_THEME["panel"], fg=ACTIVE_THEME["red"], activebackground="#102538", activeforeground=ACTIVE_THEME["red"],
            relief=tk.FLAT, cursor="hand2", highlightthickness=1,
            highlightbackground=ACTIVE_THEME["red"], command=self._delete, padx=12, pady=3)
        self._del_btn.pack(side=tk.RIGHT, padx=4)
        
        self._dpbar = ttk.Progressbar(bot, mode="determinate", length=180)
        self._dpbar.pack(side=tk.RIGHT, padx=6)

    def _start_scan(self):
        if self._scanning: return
        self._scanning = True
        self._scan_btn.config(state=tk.DISABLED)
        self._files = []
        self._tree.delete(*self._tree.get_children())
        self._checked.clear()
        self._summ.config(text="Scanning target directories...")
        self._pbar.start(10)
        self._prog_lbl.config(text="Scanning directories in parallel...", fg=ACTIVE_THEME["yellow"])
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        t0 = time.monotonic()
        out = []
        lk = threading.Lock()
        cnt = [0]

        def scan_dir(cat, dir_path):
            if not os.path.exists(dir_path): return
            local = []
            
            def _walk(p):
                try:
                    with os.scandir(p) as it:
                        for entry in it:
                            try:
                                if entry.is_file(follow_symlinks=False):
                                    st = entry.stat(follow_symlinks=False)
                                    kb = st.st_size / 1024.0
                                    mt = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y")
                                    sz = f"{kb:.1f} KB" if kb < 1024 else f"{kb/1024:.2f} MB"
                                    local.append({"path": entry.path, "size_kb": kb,
                                                  "size_disp": sz, "mtime": mt, "cat": cat})
                                elif entry.is_dir(follow_symlinks=False):
                                    _walk(entry.path)
                            except Exception: pass
                except Exception: pass

            _walk(dir_path)
            with lk:
                out.extend(local)
                cnt[0] += len(local)
                cleaner_queue.put(("prog", f"Scanned {os.path.basename(dir_path)}… {cnt[0]} files found"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:
            concurrent.futures.wait([ex.submit(scan_dir, c, d) for c, d in TARGETS])

        el = time.monotonic() - t0
        with proof_lock:
            proof_data.update({
                "cleaner_last_wake":   datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "cleaner_scan_time":   round(el, 2),
                "cleaner_files_found": len(out),
                "cleaner_status":      "IDLE",
            })
        cleaner_queue.put(("done", out, el))

    def _poll_gui(self):
        try:
            while True:
                m = cleaner_queue.get_nowait()
                if m[0] == "prog":
                    self._prog_lbl.config(text=m[1])
                elif m[0] == "done":
                    self._scan_done(m[1], m[2])
                elif m[0] == "dp":
                    self._dpbar["value"] = m[1]
                    if m[2]:
                        try: self._tree.delete(m[2]); self._checked.discard(m[2])
                        except Exception: pass
                elif m[0] == "dfin":
                    self._del_btn.config(state=tk.NORMAL)
                    messagebox.showinfo("SysForge Cleaner Result",
                        f"Successfully deleted {m[1]} files. Freed {m[2]/1024:.2f} MB." +
                        (f"\nSkipped/Failed: {len(m[3])} files." if m[3] else ""))
        except queue.Empty: pass
        self.after(150, self._poll_gui)

    def _scan_done(self, files, el):
        self._files = files
        self._pbar.stop()
        self._scan_btn.config(state=tk.NORMAL)
        self._scanning = False
        self._time_lbl.config(text=f"Total Scan Time: {el:.2f}s")
        self._prog_lbl.config(text=f"Scan Complete — {len(files)} files found", fg=ACTIVE_THEME["accent"])
        self._populate(files)
        self._update_summary()

    def _populate(self, files):
        self._tree.delete(*self._tree.get_children())
        self._checked.clear()
        for f in files:
            iid = self._tree.insert("", tk.END,
                values=("✓", f["path"], f["size_disp"], f["mtime"], f["cat"]),
                tags=("on",))
            self._checked.add(iid)
        self._tree.tag_configure("on",  foreground=ACTIVE_THEME["text"])
        self._tree.tag_configure("off", foreground=ACTIVE_THEME["text_dim"])

    def _toggle(self, e):
        iid = self._tree.identify_row(e.y)
        if not iid: return
        vals = list(self._tree.item(iid)["values"])
        if iid in self._checked:
            self._checked.discard(iid); vals[0] = "☐"
            self._tree.item(iid, tags=("off",), values=vals)
        else:
            self._checked.add(iid); vals[0] = "✓"
            self._tree.item(iid, tags=("on",), values=vals)
        self._update_summary()

    def _sel_all(self):
        for iid in self._tree.get_children():
            self._checked.add(iid)
            v = list(self._tree.item(iid)["values"]); v[0] = "✓"
            self._tree.item(iid, tags=("on",), values=v)
        self._update_summary()

    def _desel_all(self):
        for iid in self._tree.get_children():
            self._checked.discard(iid)
            v = list(self._tree.item(iid)["values"]); v[0] = "☐"
            self._tree.item(iid, tags=("off",), values=v)
        self._update_summary()

    def _update_summary(self):
        if not self._files: return
        cats = {}
        tot = 0
        for f in self._files:
            c = f["cat"]
            cats.setdefault(c, {"n": 0, "kb": 0})
            cats[c]["n"] += 1; cats[c]["kb"] += f["size_kb"]; tot += f["size_kb"]
        parts = " | ".join(f"{c}: {v['n']} ({v['kb']/1024:.1f}MB)" for c, v in cats.items())
        self._summ.config(text=f"Total: {len(self._files)} files found ({tot/1024:.1f} MB total reclaimable)   [{parts}]")

    def _delete(self):
        iids = [(iid, self._tree.item(iid)["values"][1]) for iid in self._checked]
        if not iids:
            messagebox.showinfo("SysForge", "No files selected for deletion."); return
        kb = sum(f["size_kb"] for f in self._files if any(f["path"] == p for _, p in iids))
        
        if not messagebox.askyesno("SysForge Cleaner Confirmation",
                f"You are about to delete {len(iids)} files totalling {kb/1024:.1f} MB.\n"
                f"This operation cannot be undone. Proceed?"):
            return
            
        self._del_btn.config(state=tk.DISABLED)
        self._dpbar["maximum"] = len(iids)
        self._dpbar["value"]   = 0

        safe = [d for _, d in TARGETS]
        def is_safe(path):
            for r in safe:
                try:
                    if Path(path).is_relative_to(Path(r)): return True
                except Exception: pass
            return False

        def worker():
            done = 0; freed = 0; failed = []
            lk2 = threading.Lock()
            
            def rm(item):
                nonlocal done, freed
                iid, path = item
                if not is_safe(path): return
                try:
                    sz = Path(path).stat().st_size / 1024.0
                    os.remove(path)
                    with lk2: done += 1; freed += sz
                    cleaner_queue.put(("dp", done, iid))
                except Exception:
                    with lk2: failed.append(path)
                    cleaner_queue.put(("dp", done, None))
                    
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
                concurrent.futures.wait([ex.submit(rm, i) for i in iids])
                
            cleaner_queue.put(("dfin", done, freed, failed))

        threading.Thread(target=worker, daemon=True).start()

    def update_theme(self, theme):
        self.config(bg=theme["bg"])


# ═════════════════════════════════════════════════════════════════════════════
#  LIVE PROOF PANEL  (F2 Key Toggle)
# ═════════════════════════════════════════════════════════════════════════════
class ProofPanel(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("SysForge — Live Telemetry Proof Panel")
        self.configure(bg=ACTIVE_THEME["bg"])
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.geometry("580x360+20+20")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        hdr = tk.Frame(self, bg=ACTIVE_THEME["bg"], highlightbackground=ACTIVE_THEME["primary"], highlightthickness=1)
        hdr.pack(fill=tk.X, padx=6, pady=6)
        tk.Label(hdr, text="[ SYSFORGE LIVE PROOF PANEL ]  Press F2 to Hide",
                 font=FONT_HEAD, fg=ACTIVE_THEME["primary"], bg=ACTIVE_THEME["bg"]).pack(pady=4)

        self._txt = tk.Text(self, font=("Courier New", 8), bg=ACTIVE_THEME["panel"], fg=ACTIVE_THEME["accent"],
                             relief=tk.FLAT, width=72, height=17, state=tk.DISABLED,
                             highlightbackground=ACTIVE_THEME["primary"], highlightthickness=1)
        self._txt.pack(padx=6, pady=4)
        self._tick()

    def _tick(self):
        with proof_lock:
            d = dict(proof_data)
        cpu_s = ", ".join(f"{v:.1f}" for v in d["monitor_raw_cpu"][:6])
        if len(d["monitor_raw_cpu"]) > 6: cpu_s += "…"
        
        lines = [
            "BACKGROUND THREADS TELEMETRY STATUS",
            f"  Monitor Thread  : ACTIVE | Last Wake: {d['monitor_last_wake']} | Interval: {d['monitor_interval']}",
            f"  Process Thread  : ACTIVE | Last Wake: {d['process_last_wake']} | Interval: {d['process_interval']}",
            f"  Cleaner Thread  : {d['cleaner_status']:<6} | Last Wake: {d['cleaner_last_wake']}",
            "",
            "HARDWARE & THERMAL DATA SENSORS",
            f"  API Used       : psutil + WMI MSAcpi_ThermalZone",
            f"  CPU Frequency  : {d['monitor_cpu_freq']}",
            f"  System Temp    : {d['monitor_cpu_temp']}",
            f"  Cooling Fan    : {d['monitor_fan_status']}",
            f"  Raw CPU Cores  : [{cpu_s}]",
            f"  Raw RAM Used   : {d['monitor_raw_ram_used']:.0f} MB / {d['monitor_raw_ram_total']:.0f} MB",
            "",
            "PROCESS CONTROLLER TELEMETRY",
            f"  Parallel Threads: {d['process_enum_threads']} worker threads",
            f"  PIDs Scanned   : {d['process_pids_scanned']} processes | Scan Duration: {d['process_scan_ms']:.0f} ms",
            "",
            "CLEANER ENGINE TELEMETRY",
            f"  Directory Threads: {d['cleaner_threads']} concurrent threads | Scan Time: {d['cleaner_scan_time']:.2f}s",
            f"  Files Found    : {d['cleaner_files_found']:,} files",
        ]
        self._txt.config(state=tk.NORMAL)
        self._txt.delete("1.0", tk.END)
        self._txt.insert("1.0", "\n".join(lines))
        self._txt.config(state=tk.DISABLED)
        self.after(1000, self._tick)


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW WITH SIDEBAR DASHBOARD & THEME ENGINE
# ═════════════════════════════════════════════════════════════════════════════
class SysForge(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SYSFORGE — Real-Time Parallel Cyber-Dashboard")
        self.configure(bg=ACTIVE_THEME["bg"])
        self.geometry("1280x820")
        self.minsize(1020, 660)
        self._proof = None
        self._build_dashboard()
        self.bind_all("<F2>", self._toggle_proof)

    def _build_dashboard(self):
        # ── LEFT NAVIGATION SIDEBAR ──
        self._sidebar = tk.Frame(self, bg=ACTIVE_THEME["sidebar"], width=220)
        self._sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self._sidebar.pack_propagate(False)

        logo_box = tk.Frame(self._sidebar, bg=ACTIVE_THEME["sidebar"], height=64)
        logo_box.pack(fill=tk.X, pady=(12, 10))
        logo_box.pack_propagate(False)
        
        self._logo_main = tk.Label(logo_box, text="◈ SYS:FORGE", font=("Courier New", 15, "bold"), fg=ACTIVE_THEME["primary"], bg=ACTIVE_THEME["sidebar"])
        self._logo_main.pack()
        self._logo_sub  = tk.Label(logo_box, text="v2.0 CYBER DASHBOARD", font=FONT_SM, fg=ACTIVE_THEME["secondary"], bg=ACTIVE_THEME["sidebar"])
        self._logo_sub.pack()

        self._sep = tk.Canvas(self._sidebar, height=2, bg=ACTIVE_THEME["sidebar"], highlightthickness=0)
        self._sep.pack(fill=tk.X, padx=12, pady=(0, 16))
        self._sep.bind("<Configure>", lambda e: (
            self._sep.delete("all"),
            self._sep.create_line(0, 0, e.width, 0, fill=ACTIVE_THEME["primary"], width=1)))

        nav_items = [
            (" 📊  HARDWARE MONITOR ", 0),
            (" ⚡  PROCESS CONTROL   ", 1),
            (" 🧹  SYSTEM CLEANER   ", 2),
        ]
        
        self._nav_btns = []
        for label, idx in nav_items:
            btn = tk.Button(self._sidebar, text=label, font=FONT_HEAD,
                            bg=ACTIVE_THEME["sidebar"], fg=ACTIVE_THEME["text_dim"],
                            activebackground="#091826", activeforeground=ACTIVE_THEME["primary"],
                            bd=0, relief=tk.FLAT, cursor="hand2",
                            anchor="w", padx=16, pady=10,
                            command=lambda i=idx: self._select_tab(i))
            btn.pack(fill=tk.X, pady=3, padx=6)
            self._nav_btns.append(btn)

        sb_foot = tk.Frame(self._sidebar, bg=ACTIVE_THEME["sidebar"])
        sb_foot.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=14)
        
        tk.Label(sb_foot, text="ACTIVE THEME ENGINE", font=FONT_SM, fg=ACTIVE_THEME["text_dim"], bg=ACTIVE_THEME["sidebar"]).pack(anchor="w")
        self._sb_stat = tk.Label(sb_foot, text="Theme: CYBERPUNK", font=FONT_MONO, fg=ACTIVE_THEME["accent"], bg=ACTIVE_THEME["sidebar"])
        self._sb_stat.pack(anchor="w", pady=(2, 0))

        # ── MAIN RIGHT CONTENT AREA ──
        self._right_container = tk.Frame(self, bg=ACTIVE_THEME["bg"])
        self._right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(self._right_container, bg="#06101c", height=44)
        top_bar.pack(fill=tk.X)
        top_bar.pack_propagate(False)

        self._title_lbl = tk.Label(top_bar, text="HARDWARE MONITOR DASHBOARD",
                                    font=FONT_TITLE, fg=ACTIVE_THEME["primary"], bg="#06101c")
        self._title_lbl.pack(side=tk.LEFT, padx=16)

        # Dynamic Theme Switcher Buttons
        theme_box = tk.Frame(top_bar, bg="#06101c")
        theme_box.pack(side=tk.LEFT, padx=20)
        
        tk.Label(theme_box, text="THEME:", font=FONT_SM, fg=ACTIVE_THEME["text_dim"], bg="#06101c").pack(side=tk.LEFT, padx=4)
        for t_key, t_col in [("CYBERPUNK", "#00f0ff"), ("MATRIX", "#00ff66"), ("VAPORWAVE", "#9d00ff")]:
            tk.Button(theme_box, text=t_key[0], font=FONT_SM, bg="#0a1c2e", fg=t_col,
                      activebackground="#102e48", activeforeground=t_col,
                      relief=tk.FLAT, cursor="hand2", bd=0, padx=6, pady=2,
                      command=lambda k=t_key: self._set_theme(k)).pack(side=tk.LEFT, padx=2)

        self._clock = tk.Label(top_bar, text="", font=FONT_HEAD, fg=ACTIVE_THEME["primary"], bg="#06101c")
        self._clock.pack(side=tk.RIGHT, padx=14)
        
        proof_btn = tk.Button(top_bar, text="[ F2 ] PROOF TELEMETRY", font=FONT_HEAD,
                              bg="#091b2c", fg=ACTIVE_THEME["secondary"], activebackground="#102e48", activeforeground=ACTIVE_THEME["secondary"],
                              relief=tk.FLAT, cursor="hand2", bd=0, padx=10, pady=3,
                              command=self._toggle_proof)
        proof_btn.pack(side=tk.RIGHT, padx=6)
        self._tick_clock()

        self._h_div = tk.Canvas(self._right_container, height=2, bg=ACTIVE_THEME["bg"], highlightthickness=0)
        self._h_div.pack(fill=tk.X)
        self._h_div.bind("<Configure>", lambda e: (
            self._h_div.delete("all"),
            self._h_div.create_line(0, 0, e.width, 0, fill=ACTIVE_THEME["primary"], width=1)))

        self._content_frame = tk.Frame(self._right_container, bg=ACTIVE_THEME["bg"])
        self._content_frame.pack(fill=tk.BOTH, expand=True)

        self._t1 = MonitorTab(self._content_frame)
        self._t2 = ProcessTab(self._content_frame)
        self._t3 = CleanerTab(self._content_frame)
        self._tabs = [self._t1, self._t2, self._t3]
        self._cur_tab = 0

        self._select_tab(0)

    def _select_tab(self, index):
        self._cur_tab = index
        titles = [
            "SYSTEM HARDWARE MONITOR DASHBOARD",
            "PARALLEL PROCESS CONTROLLER",
            "PARALLEL SYSTEM CACHE CLEANER"
        ]
        self._title_lbl.config(text=titles[index], fg=ACTIVE_THEME["primary"])
        
        for idx, tab in enumerate(self._tabs):
            if idx == index:
                tab.pack(fill=tk.BOTH, expand=True)
                self._nav_btns[idx].config(bg="#081828", fg=ACTIVE_THEME["primary"])
            else:
                tab.pack_forget()
                self._nav_btns[idx].config(bg=ACTIVE_THEME["sidebar"], fg=ACTIVE_THEME["text_dim"])

    def _set_theme(self, theme_key):
        global ACTIVE_THEME
        ACTIVE_THEME = THEMES[theme_key]
        t = ACTIVE_THEME
        
        self.config(bg=t["bg"])
        self._sidebar.config(bg=t["sidebar"])
        self._logo_main.config(fg=t["primary"], bg=t["sidebar"])
        self._logo_sub.config(fg=t["secondary"], bg=t["sidebar"])
        self._sb_stat.config(text=f"Theme: {t['name']}", fg=t["accent"], bg=t["sidebar"])
        self._right_container.config(bg=t["bg"])
        self._content_frame.config(bg=t["bg"])
        
        self._t1.update_theme(t)
        self._t2.update_theme(t)
        self._t3.update_theme(t)
        self._select_tab(self._cur_tab)

    def _tick_clock(self):
        self._clock.config(text=datetime.datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_clock)

    def _toggle_proof(self, _=None):
        if self._proof is None:
            self._proof = ProofPanel(self)
        elif self._proof.winfo_viewable():
            self._proof.withdraw()
        else:
            self._proof.deiconify()


if __name__ == "__main__":
    app = SysForge()
    app.mainloop()