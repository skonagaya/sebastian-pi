import time
import cv2
import json
import imutils
import dlib
import warnings
import datetime
import logging

from imutils.video.pivideostream import PiVideoStream

from picamera.array import PiRGBArray
from picamera import PiCamera

logging.basicConfig(filename="sample.log", level=logging.DEBUG)
CAMERA_WARM_UP_TIME = 5.0
ROTATE_CAMERA_180 = True
SHOW_POPUP = False
DISPLAY_MODE = "MOTION"
conf = json.load(open("conf.json"))

class Camera(object):
	"""Threaded interface for Raspberry pi Camera module."""

	MOTION="MOTION"
	FACE="FACE"

	def __init__(self):
		# load Haar Cascade face training file
		self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
		self.log = logging.getLogger("Camera")

		self.vs = None # Video stream that controls camera
		self.avg = None # Average state used for motion tracking
		self.frameCounter = 0 # Counter used to execute checks every N frames
		self.motionCounter = 0 # Trigger an action after N consecutive motion detection
		self.cameraOn = False # State of camera
		self.isBusy = False # Bit used to assert camera readiness when responding to a request
		self.lastUploaded = datetime.datetime.now() # i dont remember what this is for
		self.log.info("Camera module initialized")



	def turn_off_camera(self):
		""" Turn off Raspberry pi Camera module """

		self.log.info("Turning of camera")
		if not self.cameraOn: return

		self.isBusy = True
		self.vs.stop() # stop the camera thread
		self.cameraOn = False
		time.sleep(CAMERA_WARM_UP_TIME) # add camera cooldown
		self.isBusy = False

	def turn_on_camera(self):
		""" 
		Turn on Raspberry pi camera module and reset variables 
		Return true if successful
		"""

		self.log.info("Turning on camera")
		# Use helper class that simply captures frames
		# through RPi cam on a separate thread
		self.isBusy = True

		# the resolution actually gets resized anyways
		# framerate is optimized for rpi
		self.vs = PiVideoStream(resolution=(320, 240),framerate=32).start()
		self.avg = None
		self.frameCounter = 0
		self.motionCounter = 0
		self.cameraOn = True
		self.lastUploaded = datetime.datetime.now()
		time.sleep(CAMERA_WARM_UP_TIME)
		self.isBusy = False
		return True

	def get_current_jpeg(self,mode):

		if self.isBusy: return ("",None)

		if not self.cameraOn: self.turn_on_camera()

		# get the last frame from RPi camera
		frame = self.vs.read()

		# Do initial transformation and calibration
		frame = self.get_raw_frame(frame)

		# Add detection if mode is specified
		if mode == self.MOTION: 
			frame = self.get_motion_frame(frame)
		elif mode == self.FACE:
			frame = self.get_face_frame(frame)

		# display in a popup on the server
		if SHOW_POPUP:
			cv2.imshow("Frame", frame)
			key = cv2.waitKey(1) & 0xFF


		# prep the payload by encoding frame to jpeg
		ret, jpeg = cv2.imencode('.jpg', frame)
		return (jpeg.tostring(), None)

	def get_motion_frame(self, frame):
		"""
        Return a frame with squares around ares with motion detected in a frame.
        """

		timestamp = datetime.datetime.now()
		text = "Unoccupied"

		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		gray = cv2.GaussianBlur(gray, (21, 21), 0)

		# if the average frame is None, initialize it
		if self.avg is None:
			self.avg = gray.copy().astype("float")

			return frame

		# accumulate the weighted average between the current frame and
		# previous frames, then compute the difference between the current
		# frame and running average
		cv2.accumulateWeighted(gray, self.avg, 0.5)
		frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(self.avg))

		# threshold the delta image, dilate the thresholded image to fill
		# in holes, then find contours on thresholded image
		thresh = cv2.threshold(frameDelta, conf["delta_thresh"], 255, cv2.THRESH_BINARY)[1]
		thresh = cv2.dilate(thresh, None, iterations=2)
		cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]

		# loop over the contours
		for c in cnts:
			# if the contour is too small, ignore it
			if cv2.contourArea(c) < conf["min_area"]:
				continue

			# compute the bounding box for the contour, draw it on the frame,
			# and update the text
			(x, y, w, h) = cv2.boundingRect(c)
			cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
			text = "Occupied"

		# draw the text and timestamp on the frame
		ts = timestamp.strftime("%A %d %B %Y %I:%M:%S%p")
		cv2.putText(frame, "Room Status: {}".format(text), (10, 20),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
		cv2.putText(frame, ts, (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX,
			0.35, (0, 0, 255), 1)

		# check to see if the room is occupied
		if text == "Occupied":
			# check to see if enough time has passed between uploads
			if (timestamp - self.lastUploaded).seconds >= conf["min_upload_seconds"]:
				# increment the motion counter
				self.motionCounter += 1

				# check to see if the number of frames with consistent motion is
				# high enough
				if self.motionCounter >= conf["min_motion_frames"]:
					# update the last uploaded timestamp and reset the motion
					# counter
					self.lastUploaded = timestamp
					self.motionCounter = 0

		# otherwise, the room is not occupied
		else:
			self.motionCounter = 0

		return frame

	def get_face_frame(self, frame):
		"""
        Use Haar Cascade to detect face in a frame.
        Return a frame with squares for faces detected in a frame.
        """

		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
		for (x,y,w,h) in faces:
			cv2.rectangle(frame,(x,y),(x+w,y+h),(255,0,0),2)
			roi_gray = gray[y:y+h, x:x+w]
			roi_color = frame[y:y+h, x:x+w]

		return frame

	def get_raw_frame(self, frame):
		# get the last frame from RPi camera
		frame = self.vs.read()

		# roteate the camera 180 degrees if installed upside-down
		if ROTATE_CAMERA_180:
			rows,cols,ch  = frame.shape
			M = cv2.getRotationMatrix2D((cols/2,rows/2),180,1)
			frame = cv2.warpAffine(frame,M,(cols,rows))

		# resize the frame, convert it to grayscale, and blur it
		frame = imutils.resize(frame, width=400)

		return frame
