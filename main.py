#!/usr/bin/env python3
import subprocess
import tempfile
import json
import os
import time
import requests
import serial

#CONFIG
API_KEY = "-"   #I removed the api key!
MODEL_ID = "resistor-value-training-ipjry/3"
API_URL = f"https://detect.roboflow.com/{MODEL_ID}"

ARDUINO_PORT = "/dev/ttyACM0"   
BAUD_RATE = 115200

#COLOR TABLES
COLOR_TO_DIGIT = {
    "black": 0,
    "brown": 1,
    "red": 2,
    "orange": 3,
    "yellow": 4,
    "green": 5,
    "blue": 6,
    "violet": 7,
    "gray": 8,
    "white": 9,
}

COLOR_TO_MULTIPLIER = {
    "black": 1,
    "brown": 10,
    "red": 100,
    "orange": 1_000,
    "yellow": 10_000,
    "green": 100_000,
    "blue": 1_000_000,
    "gold": 0.1,
    "silver": 0.01,
}

COLOR_TO_TOLERANCE = {
    "brown": 1.0,
    "red": 2.0,
    "green": 0.5,
    "blue": 0.25,
    "violet": 0.1,
    "gray": 0.05,
    "gold": 5.0,
    "silver": 10.0,
}


#CAMERA
def capture_frame_to_tempfile() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp_path = tmp.name
    tmp.close()

    cmd = [
        "rpicam-jpeg",
        "-t", "1000",      
        "-n",              
        "--width", "640",
        "--height", "480",
        "-o", tmp_path,
    ]
    subprocess.run(cmd, check=True)
    return tmp_path


#RESISTOR DECODING
def decode_resistor_from_predictions(predictions):
    """
    Decode a 4-band resistor from Roboflow predictions.
    If gold is the first band left-to-right, reverse order (resistor flipped).
    """

    if len(predictions) < 3:
        print("Not enough bands detected to decode a resistor.")
        return None

    preds = sorted(predictions, key=lambda p: p["x"])
    classes = [p["class"].lower() for p in preds]

    if classes[0] == "gold":
        print("Gold detected as first band, reversing order.")
        preds.reverse()
        classes = [p["class"].lower() for p in preds]

    tolerance_band = None
    for p in reversed(preds):
        cls = p.get("class", "").lower()
        if cls in COLOR_TO_TOLERANCE:
            tolerance_band = p
            preds.remove(p)
            break

    if len(preds) < 3:
        print("Not enough non-tolerance bands after removing tolerance.")
        return None

    bands = preds[:3]
    colors = [b["class"].lower() for b in bands]

    print("Detected band colors (left to right, without tolerance):", colors)
    if tolerance_band:
        print("Detected tolerance band (rightmost):",
              tolerance_band["class"].lower())

    try:
        d1 = COLOR_TO_DIGIT[colors[0]]
        d2 = COLOR_TO_DIGIT[colors[1]]
        multiplier = COLOR_TO_MULTIPLIER[colors[2]]
    except KeyError as e:
        print("Unknown color for digit/multiplier:", e)
        return None

    ohms = (10 * d1 + d2) * multiplier

    tolerance = None
    if tolerance_band:
        tol_color = tolerance_band["class"].lower()
        tolerance = COLOR_TO_TOLERANCE.get(tol_color)

    print(f"Decoded value: {ohms} ohms")
    if tolerance is not None:
        print(f"Tolerance: +/-{tolerance}%")

    return {
        "bands": colors,
        "tolerance_band": tolerance_band["class"].lower()
        if tolerance_band else None,
        "ohms": ohms,
        "tolerance": tolerance,
    }

#SENDS IMAGE TO ROBOFLOW
def infer_resistor_value(image_path: str):
    params = {
        "api_key": API_KEY,
        "format": "json",
    }

    with open(image_path, "rb") as f:
        files = {"file": f}
        resp = requests.post(API_URL, params=params, files=files)

    if resp.status_code != 200:
        print("Roboflow error:", resp.status_code, resp.text)
        return None

    result = resp.json()
    print("Raw Roboflow result:")
    print(json.dumps(result, indent=2))

    predictions = result.get("predictions", [])
    if not predictions:
        print("No predictions returned.")
        return None

    return decode_resistor_from_predictions(predictions)


#VALUE BIN MAPPING
def map_ohms_to_bin(ohms: float) -> int:
    TRASH_BIN = 0
    BIN_WIDTH = 3000.0
    NUM_VALUE_BINS = 11

    if ohms is None or ohms <= 0:
        return TRASH_BIN

    max_val = BIN_WIDTH * NUM_VALUE_BINS 
    if ohms > max_val:
        return TRASH_BIN

    idx = int((ohms - 1) // BIN_WIDTH) + 1

    if idx < 1 or idx > NUM_VALUE_BINS:
        return TRASH_BIN

    return idx


#SERIAL CON. TO ARDUINO
def open_arduino():
    ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=2)
    time.sleep(2)
    ser.reset_input_buffer()
    return ser


def send_command(ser, cmd: str):
    """
    Send a single line command to Arduino
    "BIN:3", "SERVO:OPEN", "SERVO:CLOSE"
    """
    line = cmd.strip() + "\n"
    print("Sending to Arduino:", line.strip())
    ser.write(line.encode("ascii"))


def send_bin_to_arduino(ser, bin_index: int):
    send_command(ser, f"BIN:{bin_index}")


def main():
    img_path = capture_frame_to_tempfile()

    #debug
    #img_path = "/home/rpi5/Desktop/33ohms.jpeg" 

    print("Using image:", img_path)

    decoded = infer_resistor_value(img_path)
    if decoded is None:
        print("Could not decode resistor.")
        return

    ohms = decoded["ohms"]
    print("Measured:", ohms, "ohms")

    bin_index = map_ohms_to_bin(ohms)
    print("Selected bin:", bin_index)

    try:
        ser = open_arduino()
    except Exception as e:
        print("Failed to open Arduino serial:", e)
        return

    try:
        send_bin_to_arduino(ser, bin_index)
        time.sleep(2.0)

        send_command(ser, "SERVO:OPEN")
        time.sleep(1.0)  

        send_command(ser, "SERVO:CLOSE")
        time.sleep(0.5)

        print("Returning to bin 0")
        send_bin_to_arduino(ser, 0)
        time.sleep(2.0)

    finally:
        ser.close()

    if img_path.startswith("/tmp") and os.path.exists(img_path):
         os.remove(img_path)


if __name__ == "__main__":
    main()
