"""Show the OAK-D Pro RGB stream using DepthAI.

OAK-D / OAK-D Pro does NOT enumerate as a UVC webcam — it speaks Luxonis'
DepthAI protocol over USB, so AVFoundation and cv2.VideoCapture will never
see it. We build a tiny on-device pipeline (ColorCamera -> XLinkOut), open
the device, and read frames from the host-side queue.

Requires:  uv add depthai   (or  pip install depthai)

Usage:
  python oakd_rgb.py                 # 1080p @ 30 fps on the RGB sensor
  python oakd_rgb.py --resolution 4k
  python oakd_rgb.py --list          # enumerate connected OAK devices
"""

from __future__ import annotations

import argparse
import sys

import cv2
import depthai as dai


SIZES = {
    "720p":  (1280, 720),
    "1080p": (1920, 1080),
    "4k":    (3840, 2160),
}


def list_devices() -> int:
    devices = dai.Device.getAllAvailableDevices()
    if not devices:
        print("No OAK devices found. Check USB cable + external power on the adapter.")
        return 1
    for d in devices:
        print(f"  {d.getMxId()}  state={d.state.name}  name={d.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resolution", choices=list(SIZES), default="1080p")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--list", action="store_true",
                    help="List connected OAK devices and exit")
    args = ap.parse_args()

    if args.list:
        return list_devices()

    width, height = SIZES[args.resolution]

    # depthai v3 API: Pipeline is a context manager; nodes are built with
    # .build(socket) and outputs are obtained via requestOutput() + a host
    # queue from createOutputQueue(). XLinkOut is gone.
    with dai.Pipeline() as pipeline:
        cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
        cam_out = cam.requestOutput(
            size=(width, height),
            type=dai.ImgFrame.Type.NV12,
            fps=args.fps,
        )
        # maxSize=1 + non-blocking: siempre el frame mas reciente. Con el
        # default (maxSize=16) la cola acumula frames y q.get() devuelve el
        # mas viejo -> el feed se ve atrasado ~0.5 s.
        q = cam_out.createOutputQueue(maxSize=1, blocking=False)

        pipeline.start()
        device = pipeline.getDefaultDevice()
        usb = device.getUsbSpeed()
        print(f"Connected: MxId={device.getMxId()}  USB={usb.name}")
        if usb not in (dai.UsbSpeed.SUPER, dai.UsbSpeed.SUPER_PLUS):
            print("  WARNING: not on USB3 — 4k may stutter or fail.")
        print(f"Streaming {width}x{height} @ {args.fps} fps. Press 'q' or ESC to quit.")

        while pipeline.isRunning():
            frame = q.get()
            cv2.imshow("OAK-D Pro RGB", frame.getCvFrame())
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
