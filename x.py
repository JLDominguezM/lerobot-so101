import cv2

# 1. Initialize the camera (0 is usually the default built-in webcam)
cap = cv2.VideoCapture(0)

# Check if the camera opened successfully
if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

while True:
    # 2. Capture frame-by-frame
    # 'ret' is a boolean (True if frame is read correctly), 'frame' is the image
    ret, frame = cap.read()

    if not ret:
        print("Error: Can't receive frame. Exiting...")
        break

    # 3. Display the resulting frame in a window named 'Camera Feed'
    cv2.imshow('Camera Feed', frame)

    # 4. Wait for 1ms and check if 'q' is pressed to exit the loop
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 5. When everything is done, release the capture and close windows
cap.release()
cv2.destroyAllWindows()
