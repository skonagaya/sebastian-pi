#!/usr/bin/env python
from flask import Flask, render_template, Response
from camera import Camera
import logging
from Heartbeat import Heartbeat
import os

app = Flask(__name__)

logging.basicConfig(filename="sample.log", level=logging.DEBUG)
log = logging.getLogger("Sebastian")


@app.route('/')
def index():
    """Video streaming home page."""
    return render_template('index.html')

def gen(camera,hb,mode):
    if not hb.is_alive():
        hb = Heartbeat(cam)
        hb.start()

    if mode == "Face":
        mode = Camera.FACE
    elif mode == "Motion":
        mode = Camera.MOTION
    else:
        mode = None

    log.debug("Generating a jpeg")
    """Video streaming generator function."""
    while True:
        frame, PoI = cam.get_current_jpeg(mode)#(Camera.FACE)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed/<mode>')
def video_feed(mode):
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(cam,heartbeat,mode),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        log.info("Initializing threads before first request.")
        global cam
        global heartbeat
        cam = Camera()
        heartbeat = Heartbeat(cam)

    app.run(host='0.0.0.0', debug=True, threaded=True)
