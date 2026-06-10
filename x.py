import cv2

# 1. Initialize the video capture object. '0' is usually the default built-in webcam.
cap = cv2.VideoCapture(0)

# Check if the webcam opened correctly
if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

while True:
    # 2. Capture frame-by-frame
    ret, frame = cap.read()

    # If the frame was not grabbed successfully, break the loop
    if not ret:
        print("Error: Can't receive frame. Exiting...")
        break

    # 3. Display the resulting frame in a window named 'Camera Feed'
    cv2.imshow('Camera Feed', frame)

    # 4. Stop the feed when the 'q' key is pressed
    # cv2.waitKey(1) waits 1 millisecond for a key event
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 5. When everything is done, release the capture object and close all windows
cap.release()
cv2.destroyAllWindows()
