# Counterfeit Clicker

A Windows desktop automation tool for pixel-based button handling with a clean GUI.

It watches two button pixels and follows this logic:

- If **both buttons are red**: equip cola (**must be in slot `1`**) and autoclick.
- If **either button is green**: unequip cold (**must be in slot `1`**) and click the green button.
- Button priority when both are green: click both buttons, waiting for them to turn red.

---

## Features

- One-file GUI app (`Counterfeit Clicker.exe`)
- Global hotkeys (works while game is focused)
- Auto-save/load config from `click_config.json`
- Per-button position capture with `Ctrl+F1` / `Ctrl+F2`
- Reliable click handling for game UI (mouse movement + retries)
- Failsafe stop support (`F8` + PyAutoGUI top-left failsafe)

---

## Requirements

### For running from source

- Windows 10/11
- Python 3.10-3.13 recommended
- Packages:
  - `pyautogui`
  - `pynput`
  - `pillow`

Install:

```powershell
python -m pip install pyautogui pynput pillow
```

> Note: Python 3.14 can break `pyautogui.pixel(...)` due to Pillow compatibility in some setups.

### For end users

- Just run `Counterfeit Clicker.exe`.
- `click_config.json` will be created automatically if missing.

---

## Quick Start

1. Launch the app.
2. Open your game and hover over the first button.
3. Press `Ctrl + F1` to set Button 1.
4. Hover over the second button.
5. Press `Ctrl + F2` to set Button 2.
6. (Optional) Open **Advanced** tab, hover equipped indicator pixel, press `Ctrl + F3`.
7. Press `F7` to start/pause automation.
8. Press `F8` to quit.

---

## Hotkeys

- `Ctrl + F1`: Set Button 1 position (watch + click point)
- `Ctrl + F2`: Set Button 2 position (watch + click point)
- `Ctrl + F3`: Set equipped-indicator pixel (**Advanced tab only**)
- `Ctrl + F4`: Test click at current mouse position
- `Ctrl + F5`: Probe pixel color under mouse
- `F6`: Save config
- `F7`: Start/Pause automation
- `F8`: Quit

---

## Automation Rules

The worker loop continuously samples both watch pixels.

- If `green_1` or `green_2` is true:
  - Ensure item is unequipped.
  - Click green button area until it is no longer green.
  - Prioritize Button 1 over Button 2.
- Else if both are red:
  - Ensure item is equipped.
  - Autoclick item target.

Item autoclick target is currently set to **screen center** (`USE_SCREEN_CENTER_FOR_ITEM_AUTOCLICK = true`), which makes it resolution-agnostic.

---

## Configuration

All settings are stored in `click_config.json`.

Common fields:

- `WATCH_PIXEL_1`, `WATCH_PIXEL_2`
- `BUTTON_1`, `BUTTON_2`
- `EQUIPPED_INDICATOR_PIXEL`
- `ITEM_TOGGLE_KEY`
- `USE_SCREEN_CENTER_FOR_ITEM_AUTOCLICK`
- Timing and color tolerance values

You can edit JSON manually, but hotkeys are the easiest way to set positions.

---

## Build EXE

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name "Counterfeit Clicker" --icon counterfeit_clicker.ico click.py
```

Output:

- `dist/Counterfeit Clicker.exe`

---

## Troubleshooting

### It won’t detect/click correctly

- Re-capture button positions with `Ctrl+F1` / `Ctrl+F2`.
- Verify button pixels actually change to red/green where sampled.
- Use `Ctrl+F5` to confirm live RGB values.
- Use **Advanced > Toggle Debug** to print state sampling.

## It doesn't click the cola
- Equip your Cola ingame
- Move to the `Advanced` tab in the app
- Hover your mouse cursor over the blue box around the cola on hotbar when equipped
- Press `Ctrl + F3` to set the location the script will look to see if the cola is equipped

### It clicks only when you move your mouse

- Keep using current build: it already includes movement nudges for game input registration.
- Avoid overlays that can block game input.

### PyAutoGUI / pyscreeze import error

- Install/upgrade Pillow:

```powershell
python -m pip install --upgrade pillow
```

- If still broken, use Python 3.12 or 3.13.

---

## Project Files

- `click.py` - main app (GUI + automation loop + hotkeys)
- `click_config.json` - saved runtime config
- `counterfeit_clicker.ico` - app icon
- `build_exe.bat` - optional build helper

---

Developed by **mtm25**


