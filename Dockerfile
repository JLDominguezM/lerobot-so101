FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libusb-1.0-0 \
    libgl1 \
    && apt-get clean

RUN pip install pyrealsense2-macosx opencv-python-headless numpy