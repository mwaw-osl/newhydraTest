from math import pi,cos,sin
import requests
import os

class FiberInitializer:

    def getConcentricities(self):
        # First try to download the most recent version
        URL = "https://www.wiyn.org/hydraConcentricities.json"
        try:
            result = requests.get(URL)
        except:
            result = None
        if result:
            # If we have successfully retrieved the file, update the cache
            confile = result.text.read()
            ofile = open(self.cachedir+"/hydraConcentricities.json",'w')
            ofile.write(confile)
            ofile.close()
        else:
            self.printError("Could not fetch the most recent concentricities file from WIYN; a local copy will be used.")
            # First look in the cache
            filename = self.cachedir+"/hydraConcentricities.json"
            confile = None
            if os.path.isfile(filename):
                try:
                    confile = open(filename).read()
                    self.printMessage("Using the concentricities file:",filename)
                except:
                    self.printError("Could not open cached concentricities file:",filename)
                    confile = None
            # If that wasn't successful look in install directory
            if not confile:
                from importlib.resources import files
                cfile = files("newhydra").joinpath("data/hydraConcentricities.json")
                try:
                    confile = cfile.read_text()
                    self.printMessage("Using the package concentricities file:",cfile.as_posix())
                except:
                    self.printError("Could not open package concentricities file:",cfile.as_posix())
                    return
                """
                    confile = None
                if confile is None:
                    filename = QFileDialog.getOpenFileName(self,"Select Concentricities File",self.cachedir,"JSON (*.json);; All files (*)",options=QFileDialog.Option.DontUseNativeDialog)[0]
                    if filename!="":
                        self.printMessage("Using file "+filename+" for fiber information")
                        try:
                            confile = open(filename).read()
                        except:
                            self.printError("Could not open file:",filename)
                            return
                    else:
                        return
                """
        self.processConcentricityFile(confile)

    def processConcentricityFile(self,concdata):
        try:
            concen = eval(concdata)
        except:
            self.printError("Could not parse concentricities file.")
            return
            return processConcentricityFileOldFormat(concdata)

        FiberDB = {}
        for fibID,fibData in concen.items():
            if fibID=="modified":
                continue
            fiber = int(fibID)
            slitid = fibData["slit"]
            cable = fibData["cable"]
            status = fibData["status"]

            angle = 2*pi*fiber/self.HydraConfig["NFIBERS"]
            cangle = cos(angle)
            sangle = sin(angle)

            parkX = self.HydraConfig["PARK"]*cangle
            parkY = self.HydraConfig["PARK"]*sangle
            pivotX = self.HydraConfig["PIVOT"]*cangle
            pivotY = self.HydraConfig["PIVOT"]*sangle

            if cable=="F": slitid = -1
            FiberDB[fibID] = {"fiber":fiber,
                              "x":parkX,
                              "y":parkY,
                              "theta":angle,
                              "cable":cable,
                              "status":status,
                              "slit":slitid,
                              "object":-1,
                              "xpark":parkX,
                              "ypark":parkY,
                              "xstow":parkX,
                              "ystow":parkY,
                              "xpivot":pivotX,
                              "ypivot":pivotY,
                              "active":cable=="F" and status=="A",
                              "queued":False,
                              "parked":True,
                              "stowed":False}
        self.FiberDB = FiberDB

    def processConcentricityFileOldFormat(self,confile):
        FiberDB = {}

        preamble = True
        for line in confile.split('\n'):
            if preamble:
                if line[:4]=="#FIB":
                    preamble = False
                continue
            if line.strip()=="":
                continue
            fibid,slitid,cable,status,concentricity,theta = line.split()
            fiber = int(fibid)
            
            angle = 2*pi*fiber/self.HydraConfig["NFIBERS"]
            cangle = cos(angle)
            sangle = sin(angle)

            parkX = self.HydraConfig["PARK"]*cangle
            parkY = self.HydraConfig["PARK"]*sangle
            pivotX = self.HydraConfig["PIVOT"]*cangle
            pivotY = self.HydraConfig["PIVOT"]*sangle

            if cable=="F": slitid = -1
            FiberDB[fibid] = {"fiber":int(fibid),
                              "x":parkX,
                              "y":parkY,
                              "theta":angle,
                              "cable":cable,
                              "status":status,
                              "slit":slitid,
                              "object":-1,
                              "xpark":parkX,
                              "ypark":parkY,
                              "xstow":parkX,
                              "ystow":parkY,
                              "xpivot":pivotX,
                              "ypivot":pivotY,
                              "active":cable=="F" and status=="A",
                              "queued":False,
                              "parked":True,
                              "stowed":False}
        self.FiberDB = FiberDB

