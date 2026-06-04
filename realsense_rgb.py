"""Show the RealSense RGB stream on macOS using only OpenCV / AVFoundation.

Why: pyrealsense2 has no aarch64 wheels on macOS and the community wrappers
(pyrealsense2-macosx, pyrealsense2-silicon, ...) are broken on Apple Silicon.
The camera is a UVC device though, so we can grab the color stream directly.

The catch: RealSense exposes *multiple* UVC interfaces (depth, IR left, IR
right, color). `cv2.VideoCapture(0)` usually returns the depth/IR one, which
is the black-and-white side-by-side view. We enumerate AVFoundation devices,
match the color one by name, and force MJPG so the color sensor is selected.

Usage:
  python realsense_rgb.py                 # auto-detect + show live feed
  python realsense_rgb.py --list          # just list cameras
  python realsense_rgb.py --index 1       # force a specific index
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import cv2


RGB_NAME_HINTS = ("rgb", "color")
REALSENSE_NAME_HINTS = ("realsense", "intel(r) realsense", "d4")


def list_cameras() -> list[tuple[int, str]]:
    """Return [(av_index, name)] for video devices visible to macOS.

    Uses system_profiler. AVFoundation enumerates cameras in the same order
    system_profiler reports them, so the index returned here matches what
    cv2.VideoCapture expects.
    """
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPCameraDataType", "-json"],
            text=True, timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    data = json.loads(out)
    return [(i, c.get("_name", f"camera_{i}"))
            for i, c in enumerate(data.get("SPCameraDataType", []))]


def pick_rgb_index(cameras: list[tuple[int, str]]) -> int | None:
    """Return the index whose name looks like the RealSense color sensor."""
    realsense = [(i, n) for i, n in cameras
                 if any(h in n.lower() for h in REALSENSE_NAME_HINTS)]
    pool = realsense or cameras
    for i, name in pool:
        if any(h in name.lower() for h in RGB_NAME_HINTS):
            return i
    if len(realsense) >= 2:
        # No name hint, but if there are >=2 RealSense interfaces the color
        # one is conventionally the second.
        return realsense[1][0]
    return None


def open_capture(index: int, width: int, height: int) -> cv2.VideoCapture | None:
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        return None
    # MJPG + a color resolution forces the color sensor on RealSense; depth/IR
    # interfaces don't advertise MJPG, so a depth interface will either fail
    # to open at this format or fall back to its native (mono) format.
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    for _ in range(15):
        ok, _ = cap.read()
        if ok:
            return cap
    cap.release()
    return None


def looks_grayscale(frame) -> bool:
    """Heuristic: IR/depth interfaces deliver frames where R==G==B."""
    b, g, r = cv2.split(frame)
    return cv2.absdiff(b, g).mean() < 1.5 and cv2.absdiff(g, r).mean() < 1.5


def auto_detect(width: int, height: int) -> int | None:
    cams = list_cameras()
    if cams:
        print("Detected cameras:")
        for i, name in cams:
            print(f"  [{i}] {name}")
        prefer = pick_rgb_index(cams)
        order = ([prefer] if prefer is not None else []) + \
                [i for i, _ in cams if i != prefer]
    else:
        print("Could not enumerate via system_profiler; probing 0..4.")
        order = list(range(5))

    for i in order:
        print(f"Probing index {i}...", flush=True)
        cap = open_capture(i, width, height)
        if cap is None:
            print(f"  index {i}: would not open at MJPG/{width}x{height}")
            continue
        ok, frame = cap.read()
        cap.release()
        if not ok:
            print(f"  index {i}: opened but no frames")
            continue
        h, w = frame.shape[:2]
        if looks_grayscale(frame):
            print(f"  index {i}: frame is monochrome ({w}x{h}) — IR/depth, skip")
            continue
        print(f"  index {i}: color frame {w}x{h} -> using this one")
        return i
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=int, default=None,
                    help="Force a specific AVFoundation camera index")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--list", action="store_true",
                    help="List visible cameras and exit")
    args = ap.parse_args()

    if args.list:
        cams = list_cameras()
        if not cams:
            print("No cameras enumerated.")
            return 1
        for i, name in cams:
            print(f"  [{i}] {name}")
        return 0

    if args.index is None:
        idx = auto_detect(args.width, args.height)
        if idx is None:
            print("No RGB stream found. Try --list, then --index N manually.",
                  file=sys.stderr)
            return 1
    else:
        idx = args.index

    cap = open_capture(0, args.width, args.height)
    if cap is None:
        print(f"Could not open camera index {idx}", file=sys.stderr)
        return 1

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Showing RealSense RGB from index {idx} ({actual_w}x{actual_h}). "
          f"Press 'q' or ESC to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Frame grab failed.", file=sys.stderr)
                break
            cv2.imshow("RealSense RGB", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
