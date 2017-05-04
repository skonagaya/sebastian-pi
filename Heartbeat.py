
import logging
import time
import subprocess
import threading
import logging

logging.basicConfig(filename="sample.log", level=logging.DEBUG)

class Heartbeat(threading.Thread):
    """
    Background operations that check the state of supporing components.
    Tracks the number of conenctions made to server.
    Helper function to automatically turn off camera when not in use.
    Used to minimize wear and tear on hardware
    """

    HEARTBEAT_INTERVAL = 60.0

    def __init__(self,camera):
        super(Heartbeat,self).__init__()
        self.cam = camera
        
        self.log = logging.getLogger("Auto-sleep")
        self.log.debug("Camera auto-sleep checker initialized")
        self.connectionExists = self.connection_exist()
        return

    def run(self):
        while True:
            self.connectionExists = self.connection_exist()
            if not self.connectionExists: 
                self.cam.turn_off_camera()
                self.log.debug("No connections found, turning off Camera")
                return
            self.log.debug("Checking need for auto-sleep in " 
                + str(self.HEARTBEAT_INTERVAL) 
                + " seconds")
            time.sleep(self.HEARTBEAT_INTERVAL)
        return

    def connection_exist(self):
        """
        Return whether there are existing connections 
        """
        p = subprocess.Popen(["/home/pi/sebastian/sebastian-flask/netstat_helper.sh", ":5000"], stdout=subprocess.PIPE)
        (output, err) = p.communicate()
        num_connections = output.strip()
        num_connections = 0 if num_connections == "" else int(num_connections)
        self.log.info(str(num_connections)+ " connection(s) found.")
        return num_connections > 0
