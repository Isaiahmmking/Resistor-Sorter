# Resistor Sorter Machine (ENSC 351)

An automated resistor-sorting machine that uses a Raspberry Pi camera + a Roboflow-hosted YOLOv8 model to read resistor color bands, decode the resistance value, and command an Arduino (with CNC shield) to rotate a bin carousel and drop the resistor into the correct bin.

**Team:** Isaiah King • Mete Balci • Yuginda Ranawaka • Alex Ungureanu

---

## Table of Contents
- [Demo workflow](#demo-workflow)
- [How it works](#how-it-works)
- [Repo layout](#repo-layout)
- [Hardware](#hardware)
- [Software requirements](#software-requirements)
- [Setup](#setup)
  - [1) Mechanical bin alignment (REQUIRED)](#1-mechanical-bin-alignment-required)
  - [2) Arduino firmware](#2-arduino-firmware)
  - [3) Raspberry Pi dependencies](#3-raspberry-pi-dependencies)
  - [4) Configure `main.py`](#4-configure-mainpy)
  - [5) Camera setup](#5-camera-setup)
- [Run](#run)
- [Bin mapping logic](#bin-mapping-logic)
- [Serial command protocol](#serial-command-protocol)
- [Troubleshooting](#troubleshooting)
- [Docs](#docs)

---

## Demo workflow
1. Place **one resistor** on the top viewing platform.
2. Run `main.py` on the Raspberry Pi.
3. The Pi captures an image, sends it to Roboflow for inference, decodes the value, and selects a bin.
4. The Pi sends serial commands to the Arduino:
   - rotate to bin
   - open servo (drop)
   - close servo
   - return to **bin 0 (reset)**

---

## How it works

### Raspberry Pi (Python)
- Captures a frame using `rpicam-jpeg`
- Uploads the image to Roboflow (YOLOv8 hosted model)
- Sorts detected bands left-to-right by X-position
- If **gold** appears first, assumes the resistor is flipped and reverses the band list
- Decodes the resistor value:
  - 4-band logic: **two digits + multiplier** (tolerance is optional)
- Maps the resistance value to a **bin index**
- Sends commands to Arduino over USB serial

### Arduino (C++ / .ino)
- Receives ASCII line commands like:
  - `BIN:4`
  - `SERVO:OPEN`
  - `SERVO:CLOSE`
- Drives:
  - stepper motor (carousel positioning)
  - servo motor (drop mechanism)

---

## Repo layout
```text
.
├─ main.py                       # Pi-side: capture → Roboflow infer → decode → map → serial commands
├─ stepper_servo_controller.ino  # Arduino-side: stepper + servo controller (upload via Arduino IDE)
├─ ENSC 351 Project – How-To-Guide.pdf
├─ ENSC 351 Final Project – Resistor Sorter Machine.pdf
└─ README.md
```

---

## Hardware
Typical setup:
- Raspberry Pi 5 (or similar) + camera module
- Arduino (with CNC shield + stepper driver modules)
- Stepper motor (bin carousel)
- Servo motor (drop mechanism)
- External motor power supply (for CNC shield / stepper)
- Pi power adapter (stable 5V supply)
- 3D-printed frame + bin carousel + drop chute

---

## Software requirements
- Raspberry Pi OS (or Linux) with **Python 3**
- Arduino IDE (or equivalent) for uploading `.ino`
- Internet access (Roboflow hosted inference)
- Packages:
  - `requests`
  - `pyserial`
- Camera tools:
  - `libcamera-apps` (provides `rpicam-hello`, `rpicam-jpeg`)

---

## Setup

### 1) Mechanical bin alignment (REQUIRED)
Before sorting, align the bins to the correct reset position:

- Flip the base + bin assembly and align the numbers so:
  - **`0` on the bin layer** lines up with **`0` on the outer base**
- This is the **reset position** the machine returns to after every sort cycle.

If this alignment is off, bin selections will be wrong.

---

### 2) Arduino firmware
1. Open `stepper_servo_controller.ino` in **Arduino IDE**
2. Select the correct **Board** + **Port**
3. Upload the sketch
4. Connect CNC shield + stepper driver modules
5. Provide external motor power (do **not** rely on USB alone for motors)

Optional quick check:
- Open Serial Monitor (using the sketch’s baud rate) to confirm the Arduino is running.

---

### 3) Raspberry Pi dependencies

#### Install camera tools
```bash
sudo apt update
sudo apt install -y libcamera-apps
```

#### Create a Python virtual environment + install deps
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install requests pyserial
```

#### (Optional) Serial permissions
If you get permission errors on `/dev/ttyACM0` or `/dev/ttyUSB0`:
```bash
sudo usermod -a -G dialout $USER
sudo reboot
```

---

### 4) Configure `main.py`
Open `main.py` and edit the configuration variables:

```python
API_KEY = "YOUR_ROBOFLOW_API_KEY"
MODEL_ID = "resistor-value-training-ipjry/3"
API_URL = f"https://detect.roboflow.com/{MODEL_ID}"

ARDUINO_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
```

Find your Arduino port:
```bash
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

If the Arduino shows up as `/dev/ttyUSB0`, update `ARDUINO_PORT` accordingly.

---

### 5) Camera setup
Verify camera operation:
```bash
rpicam-hello --preview -t 0
```

Tips:
- Center camera on the resistor platform
- Ensure bands are not shadowed or reflective
- Adjust focus if needed (carefully rotate lens)
- Use consistent, diffuse lighting

---

## Run
From the project folder:
```bash
source .venv/bin/activate
python3 main.py
```

Expected behavior:
- Terminal prints detected band colors
- Terminal prints decoded resistance value (ohms)
- Terminal prints the selected bin number
- Carousel rotates → servo drops resistor → servo closes → carousel returns to **bin 0**

---

## Bin mapping logic
The sorter maps resistance values into bins using:

- `TRASH_BIN = 0`
- `BIN_WIDTH = 3000 Ω`
- `NUM_VALUE_BINS = 11`

So:
- Bin `1` covers **1–3000 Ω**
- Bin `2` covers **3001–6000 Ω**
- ...
- Bin `11` covers **30001–33000 Ω**
- Anything `<= 0` or `> 33000 Ω` goes to **bin 0**

Example:
- A **12kΩ** resistor maps to **bin 4**

---

## Serial command protocol
`main.py` sends newline-terminated ASCII commands to the Arduino:

### Rotate carousel
- `BIN:<n>`
- Example: `BIN:4`

### Drop mechanism
- `SERVO:OPEN`
- `SERVO:CLOSE`

Typical cycle:
1. `BIN:<selected>`
2. `SERVO:OPEN`
3. `SERVO:CLOSE`
4. `BIN:0` (return to reset)

---

## Troubleshooting

### Bin goes to the wrong position
- Re-check **mechanical alignment** (0-to-0 reset)
- Mechanical play can cause drift; adjust steps/angles in the Arduino sketch if needed

### Detection is inconsistent
- Improve lighting (diffuse / even)
- Ensure resistor is centered and bands are clearly visible
- Reduce glare and shadows
- Re-focus camera lens

### Serial connection errors
Confirm device exists:
```bash
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

If permission error:
```bash
sudo usermod -a -G dialout $USER
sudo reboot
```

### Roboflow inference fails
- Confirm `API_KEY` is correct
- Confirm internet access on the Pi
- Confirm model ID/version is correct

---

## Docs
- `ENSC 351 Project – How-To-Guide.pdf` — setup, calibration, and test procedure
- `ENSC 351 Final Project – Resistor Sorter Machine.pdf` — full report, architecture, limitations
