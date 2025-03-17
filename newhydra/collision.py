import random
import time
from math import cos,sin,pi,atan2,sqrt,log
from PyQt6.QtCore import Qt,pyqtSlot,pyqtSignal
import shapely
from multiprocessing import set_start_method
from .worker import Worker

PROCESS_START_METHOD = "fork"
set_start_method(PROCESS_START_METHOD)

class MPHelper:
    catalog = None
    idmap = None
    fiberGeometries = None
    footprints = None
    HydraConfig = None
MPH = MPHelper()

"""
Function to create matrix entries.

This is in global scope to allow pickling for multi-processing.

args -- either a tuple including an optID and MPHelper data structure
          or just an optID (in which case the global MPH structure is
          used)
"""
def populateMatrixEntries(args):
    if type(args)==tuple:
        optID,indata = args
    else:
        optID = args
        indata = MPH
    buttonDiameter = indata.HydraConfig["FIBERBUTTON_RADIUS"]*2
    objid = indata.idmap[optID]
    x = indata.catalog[objid]["x"]
    y = indata.catalog[objid]["y"]
    footprint = indata.footprints[optID]

    geometries = indata.fiberGeometries[optID]
    Nfibers = len(geometries)
    entries = []
    for optID2 in range(optID+1,len(indata.idmap)):
        footprint2 = indata.footprints[optID2]
        objid2 = indata.idmap[optID2]
        x0,y0 = indata.catalog[objid2]["x"],indata.catalog[objid2]["y"]
        geometries2 = indata.fiberGeometries[optID2]
        entry = getMatrixEntry(x,y,footprint,geometries,optID,optID2,x0,y0,footprint2,geometries2,buttonDiameter)
        entries.append(entry)
    return entries

def getMatrixEntry(x,y,footprint,geometries,optID,optID2,x0,y0,footprint2,geometries2,buttonDiameter):
    # Buttons always collide
    if sqrt((x-x0)*(x-x0)+(y-y0)*(y-y0))<buttonDiameter:
        return [0]
        # Fibers never overlap
    if not shapely.intersects(footprint,footprint2):
        return [1]
    overlaps = [0]*len(geometries)
    Aindex = []
    for A,GA in enumerate(geometries):
        if GA is None:
            continue
        if shapely.intersects(GA,footprint2):
            Aindex.append(A)
    Bindex = [] 
    for B,GB in enumerate(geometries2):
        if GB is None:
            continue
        if shapely.intersects(GB,footprint):
            Bindex.append(B)
    for A in Aindex:
        matches = 0
        fiberA = geometries[A]
        for B in Bindex:
            if shapely.intersects(fiberA,geometries2[B]):
                matches |= 1<<B
        overlaps[A] = matches
    return [2,overlaps]


class CollisionMatrix:

    updateProgressSignal = pyqtSignal(int)
    printMessageSignal = pyqtSignal(str)
    REOPT = False
    buttonX = None
    buttonY = None
    INITIALIZING = True

    def populateMatrixEntries(self,optID):
        MPH = MPHelper()
        MPH.catalog = self.catalog
        MPH.idmap = self.idmap
        MPH.fiberGeometries = self.fiberGeometries
        MPH.footprints = self.footprints
        MPH.HydraConfig = self.HydraConfig
        return populateMatrixEntries((optID,MPH))

    def getMatrixEntry(self,optID,optID2):
        objid = self.idmap[optID]
        x = self.catalog[objid]["x"]
        y = self.catalog[objid]["y"]
        footprint = self.footprints[optID]
        geometries = self.fiberGeometries[optID]
        footprint2 = self.footprints[optID2]
        objid2 = self.idmap[optID2]
        x0,y0 = self.catalog[objid2]["x"],self.catalog[objid2]["y"]
        geometries2 = self.fiberGeometries[optID2]
        return getMatrixEntry(x,y,footprint,geometries,optID,optID2,x0,y0,footprint2,geometries2,self.HydraConfig["FIBERBUTTON_RADIUS"]*2)

    def setButtons(self):
        rad = self.HydraConfig["FIBERBUTTON_RADIUS"]
        npts = self.HydraConfig["FIBERBUTTON_NCIRC"]
        self.buttonX = [rad*cos(i*2*pi/npts) for i in range(npts)]
        self.buttonY = [rad*sin(i*2*pi/npts) for i in range(npts)]

    def getFiber(self,fibid,coords=None):
        if self.buttonX is None:
            self.setButtons()
        sfibid = str(fibid)
        theta = self.FiberDB[sfibid]["theta"]
        fibx = self.FiberDB[sfibid]["xpivot"]
        fiby = self.FiberDB[sfibid]["ypivot"]
        if coords is None:
            x = self.FiberDB[sfibid]["xpark"]
            y = self.FiberDB[sfibid]["ypark"]
            angle = theta
            button = shapely.Polygon([(bx+x,by+y) for bx,by in zip(self.buttonX,self.buttonY)])
        else:
            if len(coords)==4:
                x,y,angle,button = coords
            else:
                x,y = coords
                angle = atan2(y,x)
                if angle<0:
                    angle += 2*pi
                button = shapely.Polygon([(bx+x,by+y) for bx,by in zip(self.buttonX,self.buttonY)])
        extent = sqrt((fibx-x)*(fibx-x)+(fiby-y)*(fiby-y))
        if extent>self.HydraConfig["MAXEXTEND"]:
            return None
        originDistance = sqrt(x*x+y*y)
        phi = angle-theta
        deflection = originDistance*sin(phi)
        originRadialDistance = originDistance*cos(phi)
        pivotRadialDistance = self.HydraConfig["PIVOT"]-originRadialDistance
        psi = atan2(deflection,pivotRadialDistance)
        if abs(psi)>self.HydraConfig["MAXANGLE"]:
            return None
        npnts = self.HydraConfig["FIBERTUBE_NSEGMENTS"]*2+2
        tx,ty = [0]*10,[0]*npnts
        lastx,lasty = x,y
        for index in range(self.HydraConfig["FIBERTUBE_NSEGMENTS"]):
            eps = self.HydraConfig["FIBERTUBE_SEGMENTS"][index+1]
            deflN = deflection*(0.5*eps*eps*eps-1.5*eps+1.)
            dN = originRadialDistance+pivotRadialDistance*eps
            rN = sqrt(dN*dN+deflN*deflN)
            phiN = atan2(deflN,dN)
            x0 = rN*cos(theta+phiN)
            y0 = rN*sin(theta+phiN)
            dx = x0-lastx
            dy = y0-lasty
            dnorm = sqrt(dx*dx+dy*dy)
            vx = -self.HydraConfig["FIBERTUBE_HALFDIAMETER"]*dy/dnorm
            vy = self.HydraConfig["FIBERTUBE_HALFDIAMETER"]*dx/dnorm

            tx[index] = lastx+vx
            ty[index] = lasty+vy
            vx *= -1
            vy *= -1
            tx[npnts-index-1] = lastx+vx
            ty[npnts-index-1] = lasty+vy
            lastx,lasty = x0,y0

        tx[npnts//2] = lastx+vx
        ty[npnts//2] = lasty+vy
        tx[npnts//2-1] = lastx-vx
        ty[npnts//2-1] = lasty-vy
        tube = shapely.Polygon([(x0,y0) for x0,y0 in zip(tx,ty)])
        geo = shapely.union(button,tube)
        shapely.prepare(geo)
        return geo

    def addCatalogObject(self,optID,objid,obj):
        #objid,obj = data
        #self.idmap.append(objid)
        x = obj["x"]
        y = obj["y"]
        angle = atan2(y,x)
        if angle<0:
            angle += 2*pi

        originDistance = sqrt(x*x+y*y)
        passThru = False
        if originDistance>self.HydraConfig["PLATE"]:
            self.printError("Object {} (objid={}) is not on the plate (x={},y={})".format(obj["name"],objid,x,y))
            passThru = True
        self.idmap.append(objid)
        self.weights.append(obj["weight"])
        geometries = []
        button = shapely.Polygon([(bx+x,by+y) for bx,by in zip(self.buttonX,self.buttonY)])
        for fibIndex,fibid in enumerate(self.fibers):
            if passThru:
                geometries.append(None)
                continue
            if obj["type"]=='F' or self.FiberDB[str(fibid)]["cable"]=='F':
                if obj["type"]!=self.FiberDB[str(fibid)]["cable"]:
                    geometries.append(None)
                    continue
            geo = self.getFiber(fibid,(x,y,angle,button))
            if geo is None:
                geometries.append(None)
                continue
            # Check that fiber won't hit parked fibers on either side
            """
            # This is commented out because parked fibers do not
            #   block fiber placements
            lo = (fibid-1)%self.HydraConfig["NFIBERS"]
            hi = (fibid+1)%self.HydraConfig["NFIBERS"]
            if (not self.FiberDB[str(lo)]["active"] and shapely.intersects(geo,self.parkedGeometries[lo])) or (not self.FiberDB[str(hi)]["active"] and shapely.intersects(geo,self.parkedGeometries[hi])):
                geometries.append(None)
                continue
            """
            self.objList[fibIndex].append(optID)
            geometries.append(geo)
        self.fiberGeometries.append(geometries)
        footprint = shapely.union_all(geometries)
        shapely.prepare(footprint)
        self.footprints.append(footprint)

    def prepPlacement(self):
        self.setButtons()

        self.fiberLists = []
        self.fiberGeometries = []
        self.footprints = []
        self.idmap = []
        self.weights = []

        self.fibers = []
        self.parkedGeometries = []
        self.FOPSindex = []
        for fibid,data in self.FiberDB.items():
            fibid = int(fibid)
            #self.parkedGeometries.append(self.getFiber(fibid))
            if data["active"]:
                if data["cable"]=="F":
                    self.FOPSindex.append(len(self.fibers))
                self.fibers.append(fibid)
        self.objList = [[] for _ in self.fibers]
        self.objListWeights = [[] for _ in self.fibers]

        for optID,(objid,obj) in enumerate(self.catalog.items()):
            self.addCatalogObject(optID,objid,obj)

    def setMatrix(self):
        """
        Wrapper routine for createMatrix(), which spawns in a worker thread
            Also displays a status bar.
        """
        from .progressbar import ProgressWindow
        worker = Worker(self.createMatrix)
        myWindow = ProgressWindow(self)
        myWindow.setTitle("Creating optimization\ncollision matrix")
        self.updateProgressSignal.connect(myWindow.updateProgress)
        self.threadPool.start(worker)
        myWindow.exec_()
        self.updateProgressSignal.disconnect(myWindow.updateProgress)

    def createMatrix(self):
        from multiprocessing import Pool,cpu_count
        self.prepPlacement()
        ncpu = cpu_count()
        if ncpu<=2:
            ncpu = 1
        else:
            ncpu -= 2
        if ncpu>8:
            ncpu = 8
        N = len(self.idmap)

        #set_start_method(PROCESS_START_METHOD)
        # 'spawn' can be slower and doesn't show progress easily
        if PROCESS_START_METHOD=="spawn":
            # spawn passes the data to each process instead of using the
            #  global MPH data structure
            indata = MPHelper()
            indata.catalog = self.catalog
            indata.idmap = self.idmap
            indata.fiberGeometries = self.fiberGeometries
            indata.footprints = self.footprints
            indata.HydraConfig = self.HydraConfig

            indices = []
            inp = []
            chunkSize = N//ncpu
            count = 0
            for i in range(ncpu):
                for j in range(chunkSize):
                    inp.append((j*ncpu+i,indata))
                    indices.append(j*ncpu+i)
                    count += 1
            while count<N:
                inp.append((count,indata))
                indices.append(count)
                count += 1
        else:
            # fork uses the global MPH data structure
            MPH.catalog = self.catalog
            MPH.idmap = self.idmap
            MPH.fiberGeometries = self.fiberGeometries
            MPH.footprints = self.footprints
            MPH.HydraConfig = self.HydraConfig

            inp = [_ for _ in range(N)]
            chunkSize = 1
        t = time.time()
        with Pool(ncpu) as pool:
            result = pool.map_async(populateMatrixEntries,inp,chunksize=chunkSize)
            PTOTAL = [10*i for i in range(10)]
            while True:
                if result.ready():
                    break
                P = int(100*(N-result._number_left)/N)
                if len(PTOTAL) and P>=PTOTAL[0]:
                    self.updateProgressSignal.emit(P)
                    del PTOTAL[0]
            MATRIX = result.get()

        if PROCESS_START_METHOD=="spawn":
            self.MATRIX = [[] for _ in range(N)]
            for index1,index2 in enumerate(indices):
                self.MATRIX[index2] = MATRIX[index1]
        else:
            self.MATRIX = MATRIX
        self.updateProgressSignal.emit(100)
        self.printMessageSignal.emit("Matrix created in {:.1f} seconds.".format(time.time()-t))

