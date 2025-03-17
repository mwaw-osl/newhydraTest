from PyQt6.QtWidgets import QFileDialog,QHeaderView
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSlot,pyqtSignal,QTimer
from pathlib import Path
from math import pi,cos
import os,pickle,datetime,time
import shapely
from astropy.wcs import WCS
from astroquery.gaia import Gaia
from astropy.time import Time
from .worker import Worker


HOME = str(Path.home())


class CatalogManager:
    # Required keywords
    headerKeywords = ["FIELDNAME","RA","DEC","LST","EXPTIME","WAVELENGTH","CABLE","OBSDATE"]
    # These keywords are optional
    headerKeywords += ["PA","GUIDEWAVELENGTH","MINFOPS","FOPSWEIGHT","BP-RP_MIN","BP-RP_MAX","GAIA_RANGE"]

    fiberSignal = pyqtSignal(dict)
    targetSignal = pyqtSignal(dict)
    imageSignal = pyqtSignal(object,float)

    def setupTable(self):
        colHead = self.FiberTable.horizontalHeader()
        for i in range(5):
            colHead.setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
        # Manually set the fiber/slit column widths (to be smaller than the default)
        for i in range(5,7):
            colHead.setSectionResizeMode(i,QHeaderView.ResizeMode.Fixed)
            colHead.resizeSection(i,35)
        self.FiberTable.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.FiberTable.setSortingEnabled(True)
        self.FiberTable.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.FiberTable.customContextMenuRequested.connect(self.fiberTableAction)

    def loadFieldFile(self,_=None,filename=None):
        if filename is None:
            filename = QFileDialog.getOpenFileName(self,"Select Target List",HOME,"Hydra files (*.coords *.hydra);; All files (*)",options=QFileDialog.Option.DontUseNativeDialog)[0]
        if filename!="":
            # We put this behind a QTimer to give the OpenFile dialog a
            #  chance to close
            QTimer.singleShot(150,lambda: self.processTargetFile(filename))

    def processHeader(self,header):
        def reportMissing(key):
            self.printError("Missing required keyword:",key)
            return False
        OK = True
        badHeaders = []
        if header["FIELDNAME"]:
            self.FIELDNAME = header["FIELDNAME"]
        else:
            OK = reportMissing("FIELDNAME")
        if header["RA"]:
            try:
                h,m,s = [float(_) for _ in header["RA"].replace(':',' ').split()]
                if h<0 or h>23 or m<0 or m>59 or s<0 or s>=60:
                    raise
                self.FIELDRA = self.str2deg(header["RA"])*15#(h+m/60.+s/3600.)*15
                self.RA = header["RA"]
            except:
                badHeaders.append("RA")
        else:
            OK = reportMissing("RA")
        if header["DEC"]:
            try:
                d,m,s = [float(_) for _ in header["DEC"].replace(':',' ').split()]
                dec = self.str2deg(header["DEC"])
                if abs(dec)>90 or m<0 or m>59 or s<0 or s>=60:
                    raise
                self.FIELDDEC = dec
                self.DEC = header["DEC"]
            except:
                badHeaders.append("DEC")
        else:
            OK = reportMissing("DEC")
        if header["PA"]:
            try:
                self.PA = float(header["PA"])
            except:
                badHeaders.append("PA")
        else:
            try:
                ZD = self.sitePars["KPNO_LAT"]-self.FIELDDEC
                self.PA = 90-ZD if ZD>0 else ZD-90
                header["PA"] = str(self.PA)
                self.printMessage("Setting PA to {:.2f}.".format(self.PA))
            except:
                self.printError("Missing keyword PA and could not set default PA from DEC")
                OK = False
        if header["LST"]:
            try:
                h,m = [float(_) for _ in header["LST"].split(':')]
                self.LST = h+m/60.
            except:
                badHeaders.append("LST")
        else:
            OK = reportMissing("LST")
        if header["EXPTIME"]:
            try:
                self.EXPTIME = float(header["EXPTIME"])/3600
            except:
                badHeaders.append("EXPTIME")
        else:
            OK = reportMissing("EXPTIME")
        if header["WAVELENGTH"]:
            try:
                self.WAVELENGTH = float(header["WAVELENGTH"])
            except:
                badHeaders.append("WAVELENGTH")
        else:
            OK = reportMissing("WAVELENGTH")
        if header["CABLE"]:
            try:
                cable = header["CABLE"].upper()
                if cable not in ["RED","BLUE"]:
                    raise
                self.CABLE = cable
            except:
                badHeaders.append("CABLE")
        else:
            OK = reportMissing("CABLE")
        if header["OBSDATE"]:
            try:
                D = header["OBSDATE"].replace("/","-").split("-")
                if len(D)==3:
                    y,m,d = [int(_) for _ in D]
                else:
                    y,m = [int(_) for _ in D]
                    d = 15
                if y<100:
                    y += 2000
                self.DATE = datetime.datetime(y,m,d)
            except:
                badHeaders.append("OBSDATE")
        else:
            OK = reportMissing("OBSDATE")
        if header["GUIDEWAVELENGTH"]:
            try:
                self.GUIDEWAVELENGTH = float(header["GUIDEWAVELENGTH"])
            except:
                badHeaders.append("GUIDEWAVELENGTH")
        else:
            self.printMessage("Setting GUIDEWAVELENGTH to 5000")
            header["GUIDEWAVELENGTH"] = str(5000)
            self.GUIDEWAVELENGTH = 5000
        if header["MINFOPS"]:
            try:
                self.MINFOPS = int(header["MINFOPS"])
            except:
                badHeaders.append("MINFOPS")
        else:
            self.printMessage("Setting MINFOPS to 3")
            self.MINFOPS = 3
            header["MINFOPS"] = str(3)
        if header["FOPSWEIGHT"]:
            try:
                self.FOPSWEIGHT = int(header["FOPSWEIGHT"])
            except:
                badHeaders.append("FOPSWEIGHT")
        else:
            self.printMessage("Setting FOPSWEIGHT to 1000")
            self.FOPSWEIGHT = 1000
            header["FOPSWEIGHT"] = str(1000)
        if header["BP-RP_MIN"]:
            try:
                self.BPRP_MIN = float(header["BP-RP_MIN"])
            except:
                badHeaders.append("BP-RP_MIN")
        else:
            self.BPRP_MIN = None
        if header["BP-RP_MAX"]:
            try:
                self.BPRP_MAX = float(header["BP-RP_MAX"])
            except:
                badHeaders.append("BP-RP_MAX")
        else:
            self.BPRP_MAX = None
        if header["GAIA_RANGE"]:
            try:
                lo,hi = header["GAIA_RANGE"].split(',')
                lo = float(lo)
                hi = float(hi)
                assert lo<hi
                self.GAIA_RANGE = [lo,hi]
            except:
                badHeaders.append("GAIA_RANGE")
        else:
            self.GAIA_RANGE = None
        for key in badHeaders:
            self.printError("Could not parse header {}: {}".format(key,header[key]))
            OK = False
        if not OK:
            return

        # Now apply header info where necessary
        self.setABCoefficients()
        self.REFRA,self.REFDEC = self.refractCoords(self.FIELDRA*pi/180,self.FIELDDEC*pi/180)
        self.WCS = WCS({"CRVAL1":self.REFRA*180/pi,"CRVAL2":self.REFDEC*180/pi,
                        "CD1_1":1,"CD1_2":0,"CD2_1":0,"CD2_2":1.,
                        "CTYPE1":"RA---TAN","CTYPE2":"DEC--TAN"})
        FiberDB = {}
        # Reset fiber data and make the CABLE fibers active
        for fibid,data in self.FiberDB.items():
            data["object"] = -1
            data["x"] = data["xpark"]
            data["y"] = data["ypark"]
            data["parked"] = True
            data["queued"] = False
            if data["cable"]=='F':
                FiberDB[fibid] = data
                continue
            data["active"] = data["status"]=="A" and data["cable"]==self.CABLE[0]
            FiberDB[fibid] = data
        self.fiberSignal.emit(FiberDB)
        self.FiberDB = FiberDB
        return header


    def processTargetFile(self,filename):
        try:
            lines = open(filename).readlines()
        except:
            self.printError("Could not open target list!")
            return

        previousAssignments = None
        header = {}
        for key in self.headerKeywords:
            header[key] = None

        catalog = {}
        # Loop through the catalog line by line; we first collect header
        #  keywords, then set a flag when they've all been found.
        headerOK = False
        for line in lines:
            line = line.rstrip()
            if line[0]=="#":
                continue
            if not headerOK:
                tmp = line.split(":")
                if tmp[0] in self.headerKeywords:
                    value = line[line.find(":")+1:].strip()
                    if value=="None":
                        value = None
                    header[tmp[0]] = value
                    continue
                elif len(tmp)>1:
                    if tmp[0]=="SCORE":
                        previousAssignments = {}
                    else:
                        self.printMessage("Unknown keyword:",tmp[0])
                    continue
                # If we've made it this far then the line is not a comment
                #  or a header keyword. In that case we should have collected
                #  all headers, so we verify that.
                headerOK = True
                header = self.processHeader(header)
                if header is None:
                    self.printError("Invalid header, exiting")
                    return
            try:
                objid = int(line[:4])
                name = line[5:35].strip()
                mag = "%5.2f"%(float(line[36:41]))
                raStr = line[42:54]
                decStr = line[55:67]
                if decStr[0] not in ['+','-']:
                    decStr = "+"+decStr[1:]
                ra = self.str2deg(raStr)*15
                dec = self.str2deg(decStr)
                objType = "O"
                weight = int(line[68:73])
                fibid = None
                slitid = None
                if previousAssignments is not None:
                    objType = line[74]
            except:
                self.printError("Could not parse the line: ",line)
                continue
            xc,yc,xs,ys = self.skyToPlate(ra,dec)
            if objType=="F":
                x,y = xc,yc
            else:
                x,y = xs,ys
            if x*x+y*y>self.HydraConfig["PLATE"]**2:
                self.printError("Object is not on the plate (x={},y={}): {}".format(x,y,line))
                continue
            catalog[objid] = {"name":name,
                              "mag":mag,
                              "RADeg":ra,
                              "DecDeg":dec,
                              "type":objType,
                              "weight":weight,
                              "ra":raStr,
                              "dec":decStr,
                              "fibid":fibid,
                              "slitid":slitid,
                              "x":x,
                              "y":y}
            if previousAssignments is not None:
                try:
                    fibid = line[76:79].strip()
                    if self.FiberDB[fibid]["active"]:
                        flag = len(line)>79 and line[79]=='*'
                        previousAssignments[objid] = [fibid,flag]
                    else:
                        self.printError("Could not assign fiber {} to object {} because the fiber is not active.".format(fibid,name))
                except:
                    pass
        if len(catalog)==0:
            self.printError("No valid objects provided.")
            return
        catalog = self.addGaiaFOPs(header,catalog)
        self.previousAssignments = previousAssignments
        self.applyCatalog(header,catalog)

    def addGaiaFOPs(self,header,catalog):
        """
        Query the Gaia DR3 source catalog for all stars with magnitudes
          10 < G < 12, increasing the range by 0.25mag in the event that
          there are not enough stars (eg., 10.25 < G < 12.25).

          Stars must have valid magnitudes and proper motions, and
          corrections for the latter are applied using the OBSDATE keyword
          and the Gaia epoch of 2016.0.
        """
        epoch = Time(self.DATE,format="datetime").decimalyear
        years = epoch-2016.0

        t = time.time()
        query = "SELECT source_id,ra,dec,pmra,pmdec,phot_g_mean_mag from gaiadr3.gaia_source WHERE DISTANCE(%f,%f,ra,dec)<0.5 and pmra is not null and phot_g_mean_mag<14 and phot_g_mean_mag is not null"%(self.FIELDRA,self.FIELDDEC)
        if self.BPRP_MAX is not None and self.BPRP_MIN is not None:
            query += " and ((phot_bp_mean_mag-phot_rp_mean_mag) between {} and {})".format(self.BPRP_MIN,self.BPRP_MAX)
        elif self.BPRP_MAX is not None:
            query += " and (phot_bp_mean_mag-phot_rp_mean_mag)<{}".format(self.BPRP_MAX)
        elif self.BPRP_MIN is not None:
            query += " and (phot_bp_mean_mag-phot_rp_mean_mag)>{}".format(self.BPRP_MIN)
        try:
            job = Gaia.launch_job(query)
            res = job.get_results()
            self.printMessage("Obtained {} stars from Gaia DR3 with G<14 in {:.2f}s".format(len(res),time.time()-t))
        except:
            self.printError("Could not query the Gaia catalog; either the archive is temporarily down or there is a problem with internet access.")
            return catalog
        # First we count the results
        Nstars = 0
        if self.GAIA_RANGE is None:
            Mlo,Mhi = 10,12
            while Mlo<14:
                Nstars = 0
                for obj in res:
                    srcid,ra,dec,pmra,pmdec,mag = obj
                    if mag>=Mlo and mag<=Mhi:
                        Nstars += 1
                if Nstars<self.MINFOPS:
                    Mlo += 0.25
                    Mhi += 0.25
                else:
                    break
            # For the unlikely event of not having enough stars
            if Mlo>=14:
                Mlo = 11.75
                Mhi = 14
                while Mlo>=10:
                    Nstars = 0
                    for obj in res:
                        srcid,ra,dec,pmra,pmdec,mag = obj
                        if mag>=Mlo and mag<=Mhi:
                            Nstars += 1
                    if Nstars<self.MINFOPS:
                        Mlo -= 0.25
                    else:
                        break
        else:
            Mlo,Mhi = self.GAIA_RANGE
        FOPS = {}
        objid = max(catalog)+1
        correction = years*1e-3/3600
        currentNames = [catalog[oid]["name"] for oid in catalog.keys()]
        for obj in res:
            srcid,ra,dec,pmra,pmdec,mag = obj
            srcid = "NWHG "+str(srcid)
            if srcid in currentNames:
                continue
            if mag<Mlo or mag>Mhi:
                continue
            cosDec = cos(dec*pi/180)
            ra += (pmra/cosDec)*correction
            dec += pmdec*correction
            ra = float(ra)%360
            dec = float(dec)
            # Convert RA/Dec to string and back to ensure saved catalogs are the same coords
            strRA = self.ra2str(ra)
            strDec = self.dec2str(dec)
            ra = self.str2deg(strRA)*15
            dec = self.str2deg(strDec)
            xc,yc,xs,ys = self.skyToPlate(ra,dec)
            FOPS[objid] = {"name":"%s"%(srcid),
                           "mag":"%5.2f"%(mag),
                           "RADeg":ra,
                           "DecDeg":dec,
                           "type":'F',
                           "weight":self.FOPSWEIGHT,
                           "ra":strRA,
                           "dec":strDec,
                           "fibid":None,
                           "slitid":None,
                           "x":xc,
                           "y":yc}
            objid += 1
        return catalog|FOPS

    def setFieldData(self,fieldData):
        self.targetSignal.emit(fieldData)

    def applyCatalog(self,header,catalog):
        # Grab an image, either from cache or download
        imgFile = "{}/{}_{}.jpeg".format(self.cachedir,self.ra2str(self.FIELDRA).replace(" ",":"),self.dec2str(self.FIELDDEC).replace(" ",":"))
        worker =  Worker(self.setImage,imgFile)
        self.threadPool.start(worker)

        # Setup the field
        fieldData = {"name":header["FIELDNAME"],
                     "raStr":header["RA"],
                     "decStr":header["DEC"],
                     "angle":float(header["PA"]),
                     "targets":catalog}
        worker2 = Worker(self.setFieldData,fieldData)
        self.threadPool.start(worker2)

        self.catalog = catalog
        self.header = header
        self.cacheKey = self.getCacheKey()
        optFile = self.getOptFile(self.cacheKey)
        self.setupOpt(optFile)
        if self.previousAssignments is not None:
            self.INITIALIZING = True
            for objid,(fibid,flag) in self.previousAssignments.items():
                forceCode = 2 if flag else 0
                fibid = int(fibid)
                self.updateFiberAssignment(objid,fibid,forceCode=forceCode,doShow=False)
            self.INITIALIZING = False
            self.showSelected()


    def getCacheKey(self):
        # Create the cache key to see if we have a pickle'd matrix
        # First, is the header the same?
        hdrKey = [_ for _ in sorted(self.header.items())]
        # Second, is the catalog the same
        catKey = [(key,[(k,v) for k,v in sorted(obj.items()) if k not in ["fibid","slitid"]]) for key,obj in sorted(self.catalog.items())]
        # Finally, are the fibers the same
        fiberKey = [(key,obj["active"]) for key,obj in sorted(self.FiberDB.items())]

        # A unique identifier is the string representation of the
        #   combination of these
        cacheText = (hdrKey+catKey+fiberKey).__repr__()
        # Convert the text to an MD5 hash to save space
        import hashlib
        cacheKey = hashlib.md5(cacheText.encode("utf-8")).hexdigest()
        return cacheKey

    def getOptFile(self,cacheKey=None):
        if not cacheKey:
            cacheKey = self.getCacheKey()
        cachefile = self.cachedir+"/catalog.cache"
        catCache = {}
        if os.path.isfile(cachefile):
            try:
                with open(cachefile,"rb") as F:
                    catCache = pickle.load(F)
            except:
                self.printMessage("Creating new catalog cache: "+cachefile)
        else:
            self.printMessage("Creating new catalog cache: "+cachefile)
        if cacheKey in catCache:
            optFile = catCache[cacheKey]
        else:
            optFile = self.cachedir+"/"+datetime.datetime.now().isoformat()+".pkl"
            catCache[cacheKey] = optFile
            with open(cachefile,"wb") as F:
                pickle.dump(catCache,F,2)
        return optFile

    def setupOpt(self,optFile):
        '''
        Try to load cached collision matrix. If not loaded, recreate it.
        '''
        data = None
        loaded = False
        if os.path.isfile(optFile):
            try:
                with open(optFile,"rb") as F:
                    data = pickle.load(F)
            except:
                pass
        if data:
            try:
                self.fiberLists,self.fiberGeometries,self.footprints,self.idmap,self.weights,self.fibers,self.parkedGeometries,self.objList,self.MATRIX,self.FOPSindex = data
                loaded = True
            except:
                pass
        if not loaded:
            self.setMatrix()
            self.dumpOptFile(optFile)

        # Reset optimization lists
        self.objListWeights = [[] for _ in self.fibers]
        self.zeroCurrentConfig()
        for fibId,objs in enumerate(self.objList):
            wts = [self.weights[i] for i in objs]
            args = sorted(range(len(wts)),key=wts.__getitem__,reverse=True)
            self.objList[fibId] = [objs[i] for i in args]
            self.objListWeights[fibId] = [wts[i] for i in args]
            self.addToCurrentConfig(None,0.,False)

    def dumpOptFile(self,optFile):
        with open(optFile,"wb") as F:
            pickle.dump([self.fiberLists,self.fiberGeometries,self.footprints,self.idmap,self.weights,self.fibers,self.parkedGeometries,self.objList,self.MATRIX,self.FOPSindex],F,2)

    def setImage(self,imgFile):
        img = None
        if os.path.isfile(imgFile):
            from PIL import Image
            try:
                img = Image.open(imgFile)
            except:
                pass
        if img is None:
            from .PS1helper import getPS1Image
            self.printMessageSignal.emit("Downloading image")
            img = getPS1Image(self.FIELDRA,self.FIELDDEC,0.,mode=3)
            if img is not None:
                img.save(imgFile)
            else:
                self.printMessageSignal.emit("Could not download the Pan-STARRS image.")
        if img is not None:
            self.imageSignal.emit(img,-self.PA)

    def addTarget(self,ra,dec,objid=None):
        raStr = self.ra2str(ra)
        decStr = self.dec2str(dec)
        # We re-calculate the RA/Dec from the strings to get the same
        #  RA/Dec as we would derive from an input catalog. This also
        #  means the refraction corrections are applied to x,y
        ra = self.str2deg(raStr)*15
        dec = self.str2deg(decStr)
        _,_,x,y = self.skyToPlate(ra,dec)
        if objid is None:
            objid = -1
            for oid in self.catalog:
                if oid>=objid:
                    objid = oid+1
        self.catalog[objid] = {"name":"PS1 sky",
                              "mag":'99.00',
                              "RADeg":ra,
                              "DecDeg":dec,
                              "type":'S',
                              "weight":0,
                              "ra":raStr,
                              "dec":decStr,
                              "fibid":None,
                              "slitid":None,
                              "x":x,
                              "y":y}
        optID = len(self.idmap)
        self.addCatalogObject(optID,objid,self.catalog[objid])

        for fibId,objs in enumerate(self.objList):
            wts = [self.weights[i] for i in objs]
            args = sorted(range(len(wts)),key=wts.__getitem__,reverse=True)
            self.objList[fibId] = [objs[i] for i in args]
            self.objListWeights[fibId] = [wts[i] for i in args]

        for i in range(len(self.MATRIX)):
            self.MATRIX[i].append(self.getMatrixEntry(i,optID))
        self.MATRIX.append(self.populateMatrixEntries(optID))
        self.updateFiberTable(self.catalog)

    def outputCatalog(self):
        if not self.catalog:
            self.printMessage("No catalog!")
            return
        OK = False
        for index,optID in self.iterateCurrentConfig():
            if optID is not None:
                OK = True
                break
        if not OK:
            self.printMessage("No assigned objects!")
            return

        filename = ""
        dialog = QFileDialog(self,"Select save name",HOME,"Hydra files (*.hydra)")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog)
        dialog.setDefaultSuffix(".hydra")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        if dialog.exec():
            filename = dialog.selectedFiles()[0]
        if filename=='':
            return
        try:
            F = open(filename,'w')
        except PermissionError:
            self.printError("Permission denied for writing file: %s"%(filename))
            return
        except:
            self.printError("Could not open file for writing: %s"%(filename))
            return

        for key in self.headerKeywords:
            F.write("{}: {}\n".format(key,self.header[key]))
        F.write("SCORE: %d\n"%(self.currentConfig.score))
        for objid,obj in self.catalog.items():
            F.write("{:>4} {:>30} {:>5} {:>12} {:>12} {:>5} {}".format(objid,obj["name"],obj["mag"],obj["ra"],obj["dec"],obj["weight"],obj["type"]))
            if obj["fibid"]:
                F.write(" {:>3}".format(obj["fibid"]))
                if self.FiberDB[str(obj["fibid"])]["queued"]:
                    F.write("*")
                else:
                    F.write(" ")
                F.write(" # slit={:>2}".format(obj["slitid"]))
            F.write("\n")
        F.close()

        # Also update the pickle cache if the catalogs are updated
        cacheKey = self.getCacheKey()
        if cacheKey!=self.cacheKey:
            optFile = self.getOptFile(cacheKey)
            self.dumpOptFile(optFile)
            self.cacheKey = cacheKey
