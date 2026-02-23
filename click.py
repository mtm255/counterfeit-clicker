import threading
import time
import ctypes
import sys
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import pyautogui
from pynput import keyboard


# ===== USER CONFIG =====
# Pixel locations to monitor for color state.
WATCH_PIXEL_1 = (1738, 681)
WATCH_PIXEL_2 = (952, 639)

# Buttons tied to each watched spot (set these to the real click points).
BUTTON_1 = (1738, 681)
BUTTON_2 = (952, 639)

# Pixel that is blue when the item is equipped.
EQUIPPED_INDICATOR_PIXEL = (1307, 1405)

# Item toggle key (press once = equip, press again = unequip).
ITEM_TOGGLE_KEY = "1"

# Click targets.
ITEM_AUTOCLICK_BUTTON = (1383, 225)

# Timing.
LOOP_DELAY_SEC = 0.05
AUTOCLICK_INTERVAL_SEC = 0.03
POST_EQUIP_DELAY_SEC = 0.08
POST_UNEQUIP_DELAY_SEC = 0.1
GREEN_CLICK_INTERVAL_SEC = 0.03
MOUSE_DOWN_UP_DELAY_SEC = 0.015
SMOOTH_MOVE_DURATION_SEC = 0.06
SMOOTH_MOVE_STEPS = 8

# Retry clicks when UI is slow.
MAX_EQUIP_RETRIES = 3
MAX_UNEQUIP_RETRIES = 3
MAX_GREEN_CLICK_ATTEMPTS = 2
DEBUG_STATE = False

# Color matching tolerance (0-255 per channel).
COLOR_TOLERANCE = 35
BLUE_TOLERANCE = 35
CHANNEL_DOMINANCE_MIN = 25

# Sample a small cross around each watched pixel to handle shade/edge changes.
SAMPLE_OFFSETS = [(0, 0), (-2, 0), (2, 0), (0, -2), (0, 2)]
MIN_SAMPLES_FOR_STATE = 2

# Click a small area around button coordinates to improve activation reliability.
# Keep this compact so we don't linger on a button for too long.
GREEN_CLICK_OFFSETS = [(0, 0), (6, 0), (-6, 0), (0, 6), (0, -6)]

# Target colors.
RED_TARGET = (172, 65, 45)
GREEN_TARGET = (58, 172, 50)
BLUE_TARGET = (90, 142, 233)
# =======================
USE_CUSTOM_TITLEBAR = True
APP_USER_MODEL_ID = "mtm25.CounterfeitClicker"
EMBEDDED_ICON_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAABLklEQVR4nO2WTQrCMBCFk9CFeA/v4La40EPo"
    "CfQ49QR6iCpItl7AVc+huGpkoAMxzd/EVBf2QaAk6bwvL00oY6NG/bt4ykuyaZVrrJwJUk2eyzgVRAxhTpnP"
    "U4vZVhg7jwQgjaJYcH559syuiwn3vUPeAkkw1/t1w48SkBqAaY6rtQHYxsgA0rL6FIMsp6AcyDwaYEiJEYBl"
    "VnWoVXYA2bQKPz7XHZAKIVwDtgskBIH92/XyEQtRxJJCCgAFEGAUSgIgGKvVbrPiyVtQGing5eS6C8x+ShJe"
    "gbHZXPPAUCl115sPgvut34uH5tyu5y76vvbH09S2HSIWgPqrpRtDg2dbEgWlGELEpAGmmIbvQ+Qso8wVIoAr"
    "flD2mxCMQkfva6q6E5HlKLJEgJ+Zx+oFDlbbVBpNl6YAAAAASUVORK5CYII="
)

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
if getattr(sys, "frozen", False):
    CONFIG_CANDIDATES = [
        Path.cwd() / "click_config.json",
        APP_DIR / "click_config.json",
        APP_DIR.parent / "click_config.json",
    ]
else:
    CONFIG_CANDIDATES = [
        Path.cwd() / "click_config.json",
        APP_DIR / "click_config.json",
    ]
CONFIG_PATH = CONFIG_CANDIDATES[0]

if sys.platform == "win32":
    USER32 = ctypes.windll.user32
    GDI32 = ctypes.windll.gdi32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
else:
    USER32 = None
    GDI32 = None


def _to_pair(value: object, fallback: tuple[int, int]) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return fallback
    return fallback


def _to_rgb(value: object, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return int(value[0]), int(value[1]), int(value[2])
        except (TypeError, ValueError):
            return fallback
    return fallback


def _to_bool(value: object, fallback: bool) -> bool:
    return value if isinstance(value, bool) else fallback


def _to_int(value: object, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _to_float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_offsets(
    value: object, fallback: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    if isinstance(value, list):
        parsed = []
        for item in value:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                try:
                    parsed.append((int(item[0]), int(item[1])))
                except (TypeError, ValueError):
                    continue
        if parsed:
            return parsed
    return fallback


def _config_dict() -> dict:
    return {
        "WATCH_PIXEL_1": list(WATCH_PIXEL_1),
        "WATCH_PIXEL_2": list(WATCH_PIXEL_2),
        "BUTTON_1": list(BUTTON_1),
        "BUTTON_2": list(BUTTON_2),
        "EQUIPPED_INDICATOR_PIXEL": list(EQUIPPED_INDICATOR_PIXEL),
        "ITEM_TOGGLE_KEY": ITEM_TOGGLE_KEY,
        "ITEM_AUTOCLICK_BUTTON": list(ITEM_AUTOCLICK_BUTTON),
        "LOOP_DELAY_SEC": LOOP_DELAY_SEC,
        "AUTOCLICK_INTERVAL_SEC": AUTOCLICK_INTERVAL_SEC,
        "POST_EQUIP_DELAY_SEC": POST_EQUIP_DELAY_SEC,
        "POST_UNEQUIP_DELAY_SEC": POST_UNEQUIP_DELAY_SEC,
        "GREEN_CLICK_INTERVAL_SEC": GREEN_CLICK_INTERVAL_SEC,
        "MOUSE_DOWN_UP_DELAY_SEC": MOUSE_DOWN_UP_DELAY_SEC,
        "SMOOTH_MOVE_DURATION_SEC": SMOOTH_MOVE_DURATION_SEC,
        "SMOOTH_MOVE_STEPS": SMOOTH_MOVE_STEPS,
        "MAX_EQUIP_RETRIES": MAX_EQUIP_RETRIES,
        "MAX_UNEQUIP_RETRIES": MAX_UNEQUIP_RETRIES,
        "MAX_GREEN_CLICK_ATTEMPTS": MAX_GREEN_CLICK_ATTEMPTS,
        "DEBUG_STATE": DEBUG_STATE,
        "COLOR_TOLERANCE": COLOR_TOLERANCE,
        "BLUE_TOLERANCE": BLUE_TOLERANCE,
        "CHANNEL_DOMINANCE_MIN": CHANNEL_DOMINANCE_MIN,
        "SAMPLE_OFFSETS": [list(x) for x in SAMPLE_OFFSETS],
        "MIN_SAMPLES_FOR_STATE": MIN_SAMPLES_FOR_STATE,
        "GREEN_CLICK_OFFSETS": [list(x) for x in GREEN_CLICK_OFFSETS],
        "RED_TARGET": list(RED_TARGET),
        "GREEN_TARGET": list(GREEN_TARGET),
        "BLUE_TARGET": list(BLUE_TARGET),
    }


def save_config() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(_config_dict(), indent=2), encoding="utf-8")


def load_config() -> None:
    global WATCH_PIXEL_1, WATCH_PIXEL_2, BUTTON_1, BUTTON_2
    global EQUIPPED_INDICATOR_PIXEL, ITEM_TOGGLE_KEY, ITEM_AUTOCLICK_BUTTON
    global LOOP_DELAY_SEC, AUTOCLICK_INTERVAL_SEC, POST_EQUIP_DELAY_SEC, POST_UNEQUIP_DELAY_SEC
    global GREEN_CLICK_INTERVAL_SEC, MOUSE_DOWN_UP_DELAY_SEC, SMOOTH_MOVE_DURATION_SEC
    global SMOOTH_MOVE_STEPS, MAX_EQUIP_RETRIES, MAX_UNEQUIP_RETRIES, MAX_GREEN_CLICK_ATTEMPTS
    global DEBUG_STATE, COLOR_TOLERANCE, BLUE_TOLERANCE, CHANNEL_DOMINANCE_MIN
    global SAMPLE_OFFSETS, MIN_SAMPLES_FOR_STATE, GREEN_CLICK_OFFSETS
    global RED_TARGET, GREEN_TARGET, BLUE_TARGET
    global CONFIG_PATH

    existing = next((p for p in CONFIG_CANDIDATES if p.exists()), None)
    if existing is not None:
        CONFIG_PATH = existing
    if not CONFIG_PATH.exists():
        save_config()
        print(f"Created default config: {CONFIG_PATH}")
        return

    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict):
            raise ValueError("Config root must be an object")
    except Exception as exc:
        print(f"[!] Failed to load {CONFIG_PATH}: {exc}. Using in-code defaults.")
        return

    WATCH_PIXEL_1 = _to_pair(cfg.get("WATCH_PIXEL_1"), WATCH_PIXEL_1)
    WATCH_PIXEL_2 = _to_pair(cfg.get("WATCH_PIXEL_2"), WATCH_PIXEL_2)
    BUTTON_1 = _to_pair(cfg.get("BUTTON_1"), BUTTON_1)
    BUTTON_2 = _to_pair(cfg.get("BUTTON_2"), BUTTON_2)
    EQUIPPED_INDICATOR_PIXEL = _to_pair(cfg.get("EQUIPPED_INDICATOR_PIXEL"), EQUIPPED_INDICATOR_PIXEL)
    ITEM_TOGGLE_KEY = str(cfg.get("ITEM_TOGGLE_KEY", ITEM_TOGGLE_KEY))
    ITEM_AUTOCLICK_BUTTON = _to_pair(cfg.get("ITEM_AUTOCLICK_BUTTON"), ITEM_AUTOCLICK_BUTTON)

    LOOP_DELAY_SEC = _to_float(cfg.get("LOOP_DELAY_SEC"), LOOP_DELAY_SEC)
    AUTOCLICK_INTERVAL_SEC = _to_float(cfg.get("AUTOCLICK_INTERVAL_SEC"), AUTOCLICK_INTERVAL_SEC)
    POST_EQUIP_DELAY_SEC = _to_float(cfg.get("POST_EQUIP_DELAY_SEC"), POST_EQUIP_DELAY_SEC)
    POST_UNEQUIP_DELAY_SEC = _to_float(cfg.get("POST_UNEQUIP_DELAY_SEC"), POST_UNEQUIP_DELAY_SEC)
    GREEN_CLICK_INTERVAL_SEC = _to_float(cfg.get("GREEN_CLICK_INTERVAL_SEC"), GREEN_CLICK_INTERVAL_SEC)
    MOUSE_DOWN_UP_DELAY_SEC = _to_float(cfg.get("MOUSE_DOWN_UP_DELAY_SEC"), MOUSE_DOWN_UP_DELAY_SEC)
    SMOOTH_MOVE_DURATION_SEC = _to_float(cfg.get("SMOOTH_MOVE_DURATION_SEC"), SMOOTH_MOVE_DURATION_SEC)
    SMOOTH_MOVE_STEPS = _to_int(cfg.get("SMOOTH_MOVE_STEPS"), SMOOTH_MOVE_STEPS)

    MAX_EQUIP_RETRIES = _to_int(cfg.get("MAX_EQUIP_RETRIES"), MAX_EQUIP_RETRIES)
    MAX_UNEQUIP_RETRIES = _to_int(cfg.get("MAX_UNEQUIP_RETRIES"), MAX_UNEQUIP_RETRIES)
    MAX_GREEN_CLICK_ATTEMPTS = _to_int(cfg.get("MAX_GREEN_CLICK_ATTEMPTS"), MAX_GREEN_CLICK_ATTEMPTS)
    DEBUG_STATE = _to_bool(cfg.get("DEBUG_STATE"), DEBUG_STATE)

    COLOR_TOLERANCE = _to_int(cfg.get("COLOR_TOLERANCE"), COLOR_TOLERANCE)
    BLUE_TOLERANCE = _to_int(cfg.get("BLUE_TOLERANCE"), BLUE_TOLERANCE)
    CHANNEL_DOMINANCE_MIN = _to_int(cfg.get("CHANNEL_DOMINANCE_MIN"), CHANNEL_DOMINANCE_MIN)
    SAMPLE_OFFSETS = _to_offsets(cfg.get("SAMPLE_OFFSETS"), SAMPLE_OFFSETS)
    MIN_SAMPLES_FOR_STATE = _to_int(cfg.get("MIN_SAMPLES_FOR_STATE"), MIN_SAMPLES_FOR_STATE)
    GREEN_CLICK_OFFSETS = _to_offsets(cfg.get("GREEN_CLICK_OFFSETS"), GREEN_CLICK_OFFSETS)

    RED_TARGET = _to_rgb(cfg.get("RED_TARGET"), RED_TARGET)
    GREEN_TARGET = _to_rgb(cfg.get("GREEN_TARGET"), GREEN_TARGET)
    BLUE_TARGET = _to_rgb(cfg.get("BLUE_TARGET"), BLUE_TARGET)


def close_enough(color: tuple[int, int, int], target: tuple[int, int, int], tolerance: int) -> bool:
    return (
        abs(color[0] - target[0]) <= tolerance
        and abs(color[1] - target[1]) <= tolerance
        and abs(color[2] - target[2]) <= tolerance
    )


def get_pixel(point: tuple[int, int]) -> tuple[int, int, int]:
    x, y = point

    # Python 3.14 can break pyautogui.pixel() due to pyscreeze/Pillow compatibility.
    # On Windows, use the native GetPixel API to avoid that dependency.
    if USER32 and GDI32:
        hdc = USER32.GetDC(0)
        if not hdc:
            raise RuntimeError("GetDC failed while reading screen pixel")
        try:
            value = GDI32.GetPixel(hdc, x, y)
        finally:
            USER32.ReleaseDC(0, hdc)

        if value == -1:
            raise RuntimeError(f"GetPixel failed at ({x}, {y})")

        r = value & 0xFF
        g = (value >> 8) & 0xFF
        b = (value >> 16) & 0xFF
        return (r, g, b)

    return pyautogui.pixel(x, y)


def is_item_equipped() -> bool:
    indicator_color = get_pixel(EQUIPPED_INDICATOR_PIXEL)
    return close_enough(indicator_color, BLUE_TARGET, BLUE_TOLERANCE)


def click_point(point: tuple[int, int]) -> None:
    x, y = point
    smooth_move_to(x, y)

    # Use native Windows mouse input for game compatibility.
    if USER32:
        nudge_mouse_activity()
        USER32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(MOUSE_DOWN_UP_DELAY_SEC)
        USER32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        return

    # Fallback for non-Windows.
    pyautogui.moveTo(x, y, duration=0)
    pyautogui.mouseDown(button="left")
    time.sleep(MOUSE_DOWN_UP_DELAY_SEC)
    pyautogui.mouseUp(button="left")


def nudge_mouse_activity() -> None:
    if not USER32:
        return

    # Some games only register click targets after relative pointer movement.
    USER32.mouse_event(MOUSEEVENTF_MOVE, 1, 0, 0, 0)
    time.sleep(0.005)
    USER32.mouse_event(MOUSEEVENTF_MOVE, -1, 0, 0, 0)
    time.sleep(0.005)


def smooth_move_to(x: int, y: int) -> None:
    target_x = int(x)
    target_y = int(y)
    start_x, start_y = pyautogui.position()

    # If already close, snap directly.
    if abs(start_x - target_x) <= 1 and abs(start_y - target_y) <= 1:
        if USER32:
            USER32.SetCursorPos(target_x, target_y)
        else:
            pyautogui.moveTo(target_x, target_y, duration=0)
        return

    steps = max(1, SMOOTH_MOVE_STEPS)
    sleep_per_step = max(0.0, SMOOTH_MOVE_DURATION_SEC / steps)

    for i in range(1, steps + 1):
        t = i / steps
        # Smoothstep easing for human-like acceleration/deceleration.
        eased = t * t * (3 - 2 * t)
        mx = int(round(start_x + (target_x - start_x) * eased))
        my = int(round(start_y + (target_y - start_y) * eased))
        if USER32:
            USER32.SetCursorPos(mx, my)
        else:
            pyautogui.moveTo(mx, my, duration=0)
        if i < steps:
            time.sleep(sleep_per_step)


def print_probe() -> None:
    x, y = pyautogui.position()
    color = get_pixel((x, y))
    print(f"[probe] pos=({x}, {y}) rgb={color}")


def click_mouse_position() -> None:
    x, y = pyautogui.position()
    click_point((x, y))
    print(f"Test clicked at ({x}, {y})")


def sample_points(center: tuple[int, int]) -> list[tuple[int, int, int]]:
    cx, cy = center
    samples: list[tuple[int, int, int]] = []
    for ox, oy in SAMPLE_OFFSETS:
        samples.append(get_pixel((cx + ox, cy + oy)))
    return samples


def is_red_like(color: tuple[int, int, int]) -> bool:
    r, g, b = color
    return close_enough(color, RED_TARGET, COLOR_TOLERANCE) or (
        r - g >= CHANNEL_DOMINANCE_MIN and r - b >= CHANNEL_DOMINANCE_MIN
    )


def is_green_like(color: tuple[int, int, int]) -> bool:
    r, g, b = color
    return close_enough(color, GREEN_TARGET, COLOR_TOLERANCE) or (
        g - r >= CHANNEL_DOMINANCE_MIN and g - b >= CHANNEL_DOMINANCE_MIN
    )


def read_states() -> tuple[bool, bool, bool, bool]:
    p1_samples = sample_points(WATCH_PIXEL_1)
    p2_samples = sample_points(WATCH_PIXEL_2)
    red_1 = sum(1 for c in p1_samples if is_red_like(c)) >= MIN_SAMPLES_FOR_STATE
    red_2 = sum(1 for c in p2_samples if is_red_like(c)) >= MIN_SAMPLES_FOR_STATE
    green_1 = sum(1 for c in p1_samples if is_green_like(c)) >= MIN_SAMPLES_FOR_STATE
    green_2 = sum(1 for c in p2_samples if is_green_like(c)) >= MIN_SAMPLES_FOR_STATE

    if DEBUG_STATE:
        print(
            f"[state] p1_samples={p1_samples} p2_samples={p2_samples} "
            f"r1={red_1} r2={red_2} g1={green_1} g2={green_2}"
        )

    return red_1, red_2, green_1, green_2


def is_button_green(watch_pixel: tuple[int, int]) -> bool:
    samples = sample_points(watch_pixel)
    return sum(1 for c in samples if is_green_like(c)) >= MIN_SAMPLES_FOR_STATE


running_event = threading.Event()
exit_event = threading.Event()
key_controller = keyboard.Controller()
ctrl_pressed = False
global_listener: keyboard.Listener | None = None
ui_message = ""


def press_item_toggle_key() -> None:
    key_controller.press(ITEM_TOGGLE_KEY)
    time.sleep(0.01)
    key_controller.release(ITEM_TOGGLE_KEY)


def ensure_equipped() -> None:
    if is_item_equipped():
        return

    for _ in range(MAX_EQUIP_RETRIES):
        press_item_toggle_key()
        time.sleep(POST_EQUIP_DELAY_SEC)
        if is_item_equipped():
            return


def ensure_unequipped() -> None:
    if not is_item_equipped():
        return

    for _ in range(MAX_UNEQUIP_RETRIES):
        press_item_toggle_key()
        time.sleep(POST_UNEQUIP_DELAY_SEC)
        if not is_item_equipped():
            return


def click_with_retries(point: tuple[int, int], retries: int, interval_sec: float) -> None:
    for i in range(retries):
        click_point(point)
        if i < retries - 1:
            time.sleep(interval_sec)


def click_area_until_not_green(
    watch_pixel: tuple[int, int],
    center: tuple[int, int],
    offsets: list[tuple[int, int]],
    max_attempts: int,
    interval_sec: float,
) -> None:
    cx, cy = center
    for _ in range(max_attempts):
        if not is_button_green(watch_pixel):
            return
        for ox, oy in offsets:
            click_point((cx + ox, cy + oy))
            time.sleep(interval_sec)
            if not is_button_green(watch_pixel):
                return


def set_button_slot(slot: int) -> None:
    global WATCH_PIXEL_1, WATCH_PIXEL_2, BUTTON_1, BUTTON_2

    x, y = pyautogui.position()
    point = (int(x), int(y))

    if slot == 1:
        WATCH_PIXEL_1 = point
        BUTTON_1 = point
    elif slot == 2:
        WATCH_PIXEL_2 = point
        BUTTON_2 = point
    else:
        return

    save_config()
    publish_message(f"Successfully set position for Button {slot}: {point}")


def publish_message(text: str) -> None:
    global ui_message
    ui_message = text
    print(text)


def worker() -> None:
    while not exit_event.is_set():
        if not running_event.is_set():
            time.sleep(0.05)
            continue

        try:
            red_1, red_2, green_1, green_2 = read_states()
            if green_1 or green_2:
                ensure_unequipped()
                # Focus one button at a time; prioritize button 1 when both are green.
                if green_1:
                    click_area_until_not_green(
                        WATCH_PIXEL_1,
                        BUTTON_1,
                        GREEN_CLICK_OFFSETS,
                        MAX_GREEN_CLICK_ATTEMPTS,
                        GREEN_CLICK_INTERVAL_SEC,
                    )
                elif green_2:
                    click_area_until_not_green(
                        WATCH_PIXEL_2,
                        BUTTON_2,
                        GREEN_CLICK_OFFSETS,
                        MAX_GREEN_CLICK_ATTEMPTS,
                        GREEN_CLICK_INTERVAL_SEC,
                    )
                time.sleep(LOOP_DELAY_SEC)
                continue

            red_only = red_1 and red_2 and not (green_1 or green_2)
            if red_only:
                ensure_equipped()
                click_point(ITEM_AUTOCLICK_BUTTON)
                time.sleep(AUTOCLICK_INTERVAL_SEC)
                continue

            time.sleep(LOOP_DELAY_SEC)

        except pyautogui.FailSafeException:
            # Move mouse to top-left corner to instantly stop pyautogui actions.
            running_event.clear()
            print("[!] PyAutoGUI fail-safe triggered. Automation paused.")
            time.sleep(0.2)
        except Exception as exc:
            running_event.clear()
            print(f"[!] Worker error: {exc}. Automation paused.")
            time.sleep(0.2)


def toggle_debug() -> bool:
    global DEBUG_STATE
    DEBUG_STATE = not DEBUG_STATE
    return DEBUG_STATE


def toggle_running() -> bool:
    if running_event.is_set():
        running_event.clear()
        return False
    running_event.set()
    return True


def stop_and_exit() -> None:
    running_event.clear()
    exit_event.set()
    if global_listener is not None:
        global_listener.stop()


def on_global_key_press(key: keyboard.Key | keyboard.KeyCode):
    global ctrl_pressed

    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        ctrl_pressed = True
        return

    try:
        if ctrl_pressed and key == keyboard.Key.f1:
            set_button_slot(1)
            return
        if ctrl_pressed and key == keyboard.Key.f2:
            set_button_slot(2)
            return
        if ctrl_pressed and key == keyboard.Key.f4:
            click_mouse_position()
            publish_message("Test click sent.")
        elif ctrl_pressed and key == keyboard.Key.f5:
            print_probe()
            x, y = pyautogui.position()
            color = get_pixel((x, y))
            publish_message(f"Probe ({x}, {y}) rgb={color}")
        elif key == keyboard.Key.f6:
            save_config()
            publish_message(f"Config saved: {CONFIG_PATH}")
        elif key == keyboard.Key.f7:
            running = toggle_running()
            publish_message("Automation running." if running else "Automation paused.")
        elif key == keyboard.Key.f8:
            publish_message("Quit requested.")
            stop_and_exit()
            return False
    except Exception as exc:
        publish_message(f"[!] Hotkey error: {exc}")


def on_global_key_release(key: keyboard.Key | keyboard.KeyCode):
    global ctrl_pressed
    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        ctrl_pressed = False


class ClickerGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Counterfeit Clicker")
        self.root.geometry("700x500")
        self.root.resizable(False, False)
        self.root.overrideredirect(USE_CUSTOM_TITLEBAR)
        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)
        self._hicon = None
        self._photo_icon = None
        self.apply_window_icon()
        self._drag_start_x = 0
        self._drag_start_y = 0
        if USE_CUSTOM_TITLEBAR:
            self.root.after(50, self.ensure_taskbar_presence)

        self.style = ttk.Style()
        try:
            self.style.theme_use("vista")
        except tk.TclError:
            try:
                self.style.theme_use("clam")
            except tk.TclError:
                pass
        self.style.configure("Root.TFrame", background="#0b1220")
        self.style.configure("Card.TFrame", background="#111827")
        self.style.configure("TopCard.TFrame", background="#111827")
        self.style.configure("Title.TLabel", font=("Segoe UI Semibold", 17), background="#0b1220", foreground="#f8fafc")
        self.style.configure("Subtitle.TLabel", font=("Segoe UI", 10), background="#0b1220", foreground="#94a3b8")
        self.style.configure("Status.TLabel", font=("Segoe UI Semibold", 11), background="#111827", foreground="#e2e8f0")
        self.style.configure("Body.TLabel", font=("Segoe UI", 10), background="#0b1220", foreground="#cbd5e1")
        self.style.configure("Footer.TLabel", font=("Segoe UI", 9), background="#0b1220", foreground="#94a3b8")
        self.style.configure("Tip.TLabelframe", background="#111827", foreground="#cbd5e1")
        self.style.configure("Tip.TLabelframe.Label", background="#111827", foreground="#cbd5e1")

        self.status_var = tk.StringVar(value="Status: Paused")
        self.debug_var = tk.StringVar(value=f"Debug: {'ON' if DEBUG_STATE else 'OFF'}")
        self.msg_var = tk.StringVar(value=f"Config: {CONFIG_PATH}")
        self.btn_colors = {
            "primary": ("#2563eb", "#1d4ed8"),
            "secondary": ("#1f2937", "#111827"),
            "danger": ("#dc2626", "#b91c1c"),
        }

        if USE_CUSTOM_TITLEBAR:
            shell = tk.Frame(root, bg="#0b1220", bd=0, highlightthickness=1, highlightbackground="#1f2937")
            shell.pack(fill="both", expand=True)

            title_bar = tk.Frame(shell, bg="#0b1220", bd=0, highlightthickness=0, height=32)
            title_bar.pack(fill="x")
            title_bar.pack_propagate(False)

            # Empty left area keeps drag target without duplicate title text.
            tk.Frame(title_bar, bg="#0b1220", bd=0, highlightthickness=0).pack(side="left", fill="x", expand=True)

            close_btn = tk.Button(
                title_bar,
                text="x",
                command=self.on_quit,
                bg="#0b1220",
                fg="#94a3b8",
                activebackground="#1f2937",
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                width=3,
                cursor="hand2",
                font=("Segoe UI Semibold", 10),
                highlightthickness=0,
            )
            close_btn.pack(side="right")

            min_btn = tk.Button(
                title_bar,
                text="-",
                command=self.on_minimize,
                bg="#0b1220",
                fg="#94a3b8",
                activebackground="#111827",
                activeforeground="#ffffff",
                relief="flat",
                bd=0,
                width=3,
                cursor="hand2",
                font=("Segoe UI Semibold", 12),
                highlightthickness=0,
            )
            min_btn.pack(side="right")

            title_bar.bind("<ButtonPress-1>", self.start_window_drag)
            title_bar.bind("<B1-Motion>", self.drag_window)
            parent = shell
            container_padding = (12, 4, 12, 12)
        else:
            parent = root
            container_padding = (12, 12, 12, 12)

        container = ttk.Frame(parent, padding=container_padding, style="Root.TFrame")
        container.pack(fill="both", expand=True)
        root.configure(bg="#0b1220")

        ttk.Label(container, text="Counterfeit Clicker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(container, text="Automation Control Panel", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))

        top_card = ttk.Frame(container, padding=(12, 10), style="TopCard.TFrame")
        top_card.pack(fill="x", pady=(0, 8))
        ttk.Label(top_card, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.debug_status_label = ttk.Label(top_card, textvariable=self.debug_var, style="Status.TLabel")
        self.debug_status_label.grid(row=0, column=1, sticky="w", padx=(20, 0))
        ttk.Label(top_card, textvariable=self.msg_var, style="Body.TLabel", wraplength=650, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        tab_header = tk.Frame(container, bg="#0b1220", bd=0, highlightthickness=0)
        tab_header.pack(fill="x", pady=(0, 0))
        self.main_tab_btn = self.make_tab_button(tab_header, "Main", lambda: self.show_tab("main"))
        self.main_tab_btn.pack(side="left", padx=(0, 8))
        self.advanced_tab_btn = self.make_tab_button(tab_header, "Advanced", lambda: self.show_tab("advanced"))
        self.advanced_tab_btn.pack(side="left")

        tab_content = tk.Frame(container, bg="#111827", bd=0, highlightthickness=0)
        tab_content.pack(fill="both", expand=True, pady=(0, 0))
        main_tab = ttk.Frame(tab_content, padding=12, style="Card.TFrame")
        advanced_tab = ttk.Frame(tab_content, padding=12, style="Card.TFrame")
        self.tabs = {"main": main_tab, "advanced": advanced_tab}
        self.active_tab = "main"

        main_actions = tk.Frame(main_tab, bg="#111827", bd=0, highlightthickness=0)
        main_actions.pack(fill="x")
        main_actions.columnconfigure(0, weight=1)
        main_actions.columnconfigure(1, weight=1)
        main_actions.columnconfigure(2, weight=1)
        self.make_button(main_actions, "Start / Pause (F7)", self.on_toggle_running, "primary").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        self.make_button(main_actions, "Save Config (F6)", self.on_save_config, "secondary").grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        self.make_button(main_actions, "Quit (F8)", self.on_quit, "danger").grid(row=0, column=2, sticky="ew")

        tip_box = ttk.LabelFrame(main_tab, text="Button Position Setup", padding=10, style="Tip.TLabelframe")
        tip_box.pack(fill="x", pady=(12, 0))
        ttk.Label(
            tip_box,
            text="Hold your mouser over the first button and press Ctrl + F1.\n"
            "Hold your mouse over the second button and press Ctrl + F2.",
            style="Body.TLabel",
            justify="left",
        ).pack(anchor="w")

        adv_actions = tk.Frame(advanced_tab, bg="#111827", bd=0, highlightthickness=0)
        adv_actions.pack(fill="x")
        adv_actions.columnconfigure(0, weight=1)
        adv_actions.columnconfigure(1, weight=1)
        adv_actions.columnconfigure(2, weight=1)
        self.make_button(adv_actions, "Test Click (Ctrl+F4)", self.on_test_click, "secondary").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        self.make_button(adv_actions, "Probe Pixel (Ctrl+F5)", self.on_probe, "secondary").grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        self.make_button(adv_actions, "Toggle Debug", self.on_toggle_debug, "secondary").grid(
            row=0, column=2, sticky="ew"
        )

        hotkeys_box = ttk.LabelFrame(advanced_tab, text="Hotkeys", padding=10, style="Tip.TLabelframe")
        hotkeys_box.pack(fill="x", pady=(12, 0))
        ttk.Label(
            hotkeys_box,
            text="Ctrl + F1: Set Button 1 Position\n"
            "Ctrl + F2: Set Button 2 Position\n"
            "Ctrl + F4: Test Click\n"
            "Ctrl + F5: Probe Pixel\n"
            "F6: Save Config   F7: Start/Pause   F8: Quit",
            style="Body.TLabel",
            justify="left",
        ).pack(anchor="w")

        ttk.Label(
            container,
            text="Developed by mtm25",
            style="Footer.TLabel",
        ).pack(anchor="e", pady=(8, 0))

        # Keep familiar hotkeys available while GUI is focused.
        root.bind("<Control-F4>", lambda _e: self.on_test_click())
        root.bind("<Control-F5>", lambda _e: self.on_probe())
        root.bind("<F6>", lambda _e: self.on_save_config())
        root.bind("<F7>", lambda _e: self.on_toggle_running())
        root.bind("<F8>", lambda _e: self.on_quit())
        root.bind("<Control-F1>", lambda _e: set_button_slot(1))
        root.bind("<Control-F2>", lambda _e: set_button_slot(2))

        self.show_tab("main")
        self.refresh_status()

    def ensure_taskbar_presence(self) -> None:
        if sys.platform != "win32" or USER32 is None:
            return
        try:
            hwnds = []
            direct_hwnd = self.root.winfo_id()
            if direct_hwnd:
                hwnds.append(direct_hwnd)
            parent_hwnd = USER32.GetParent(direct_hwnd)
            if parent_hwnd and parent_hwnd not in hwnds:
                hwnds.append(parent_hwnd)

            for hwnd in hwnds:
                ex_style = USER32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ex_style = (ex_style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
                USER32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
                USER32.SetWindowPos(
                    hwnd,
                    0,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
                )

            # Force shell refresh so the app appears in taskbar.
            self.root.withdraw()
            self.root.after(15, self.root.deiconify)
            self.root.after(30, self.apply_window_icon)
        except Exception:
            pass

    def apply_window_icon(self) -> None:
        try:
            self._photo_icon = tk.PhotoImage(data=EMBEDDED_ICON_PNG_BASE64)
            self.root.iconphoto(True, self._photo_icon)
        except tk.TclError:
            pass

        icon_path = APP_DIR / "counterfeit_clicker.ico"
        if not icon_path.exists():
            return

        try:
            self.root.iconbitmap(str(icon_path))
        except tk.TclError:
            pass

        if sys.platform != "win32" or USER32 is None:
            return

        try:
            self._hicon = USER32.LoadImageW(
                0,
                str(icon_path),
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE,
            )
            if not self._hicon:
                return

            hwnds = []
            direct_hwnd = self.root.winfo_id()
            if direct_hwnd:
                hwnds.append(direct_hwnd)
            parent_hwnd = USER32.GetParent(direct_hwnd)
            if parent_hwnd and parent_hwnd not in hwnds:
                hwnds.append(parent_hwnd)

            for hwnd in hwnds:
                USER32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, self._hicon)
                USER32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, self._hicon)
        except Exception:
            pass

    def make_button(self, parent: tk.Widget, text: str, command, kind: str) -> tk.Button:
        bg, hover = self.btn_colors[kind]
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg="#f8fafc",
            activebackground=hover,
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
            highlightthickness=0,
        )
        btn.bind("<Enter>", lambda _e: btn.config(bg=hover))
        btn.bind("<Leave>", lambda _e: btn.config(bg=bg))
        return btn

    def make_tab_button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg="#1f2937",
            fg="#94a3b8",
            activebackground="#111827",
            activeforeground="#f8fafc",
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
            highlightthickness=0,
        )
        return btn

    def show_tab(self, tab_name: str) -> None:
        if tab_name == self.active_tab and self.tabs[tab_name].winfo_ismapped():
            return

        for frame in self.tabs.values():
            frame.pack_forget()
        self.tabs[tab_name].pack(fill="both", expand=True)
        self.active_tab = tab_name

        if tab_name == "main":
            self.main_tab_btn.config(bg="#111827", fg="#f8fafc")
            self.advanced_tab_btn.config(bg="#1f2937", fg="#94a3b8")
            self.debug_status_label.grid_remove()
        else:
            self.main_tab_btn.config(bg="#1f2937", fg="#94a3b8")
            self.advanced_tab_btn.config(bg="#111827", fg="#f8fafc")
            self.debug_status_label.grid()

    def start_window_drag(self, event) -> None:
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def drag_window(self, event) -> None:
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def on_minimize(self) -> None:
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.bind("<Map>", self.on_restore, add="+")

    def on_restore(self, _event) -> None:
        def _restore() -> None:
            self.root.overrideredirect(True)
            self.ensure_taskbar_presence()

        self.root.after(10, _restore)

    def set_message(self, text: str) -> None:
        self.msg_var.set(text)
        print(text)

    def refresh_status(self) -> None:
        if ui_message:
            self.msg_var.set(ui_message)
        self.status_var.set(f"Status: {'Running' if running_event.is_set() else 'Paused'}")
        self.debug_var.set(f"Debug: {'ON' if DEBUG_STATE else 'OFF'}")
        if not exit_event.is_set():
            self.root.after(200, self.refresh_status)

    def on_toggle_running(self) -> None:
        running = toggle_running()
        publish_message("Automation running." if running else "Automation paused.")

    def on_toggle_debug(self) -> None:
        debug = toggle_debug()
        publish_message(f"Debug state {'ON' if debug else 'OFF'}.")

    def on_probe(self) -> None:
        try:
            print_probe()
            x, y = pyautogui.position()
            color = get_pixel((x, y))
            publish_message(f"Probe ({x}, {y}) rgb={color}")
        except Exception as exc:
            publish_message(f"[!] Probe failed: {exc}")

    def on_test_click(self) -> None:
        try:
            click_mouse_position()
            publish_message("Test click sent.")
        except Exception as exc:
            publish_message(f"[!] Test click failed: {exc}")

    def on_save_config(self) -> None:
        try:
            save_config()
            publish_message(f"Config saved: {CONFIG_PATH}")
        except Exception as exc:
            publish_message(f"[!] Config save failed: {exc}")

    def on_quit(self) -> None:
        publish_message("Quit requested.")
        stop_and_exit()
        self.root.after(100, self.root.destroy)


def main() -> None:
    global global_listener

    load_config()

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.0

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    global_listener = keyboard.Listener(on_press=on_global_key_press, on_release=on_global_key_release)
    global_listener.start()
    root = tk.Tk()
    ClickerGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
