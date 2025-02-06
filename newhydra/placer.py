import random
import time
from math import cos,sin,pi,atan2,sqrt,log
from PyQt6.QtCore import Qt,pyqtSlot,pyqtSignal
import shapely
from .worker import Worker

class FiberPlacer:

    updateOptProgressSignal = pyqtSignal(int)
    updateScoreSignal = pyqtSignal(int)
    REOPT = False
    INITIALIZING = True
    NFOPS = 0
    bestID = []

    def checkCollision(self,fibIndex,optID,fibIndex2,optID2):
        """
        Check if two fiber/ojbect pairs collide.
        """
        if optID2<optID:
            M = self.MATRIX[optID2][optID-(optID2+1)]
            fibA,fibB = fibIndex2,fibIndex
        else:
            M = self.MATRIX[optID][optID2-(optID+1)]
            fibA,fibB = fibIndex,fibIndex2
        # Definite collision
        if M[0]==0:
            return True
        # Possible collision -- compare overlap list
        elif M[0]==2:
            overlaps = M[1][fibA]
            if overlaps&(1<<fibB):
                return True
        return False

    def addObjectToConfiguration(self,fibIndex,optID,forceCode=0):
        # forceCode: 0=Never force, 1=Force non-manual, 2=Force always
        isFOP = fibIndex in self.FOPSindex
        removed = []
        # Is this the same object?
        oldID = self.getCurrentConfigID(fibIndex)
        if oldID==optID and forceCode!=2:
            return None
        # Remove the current assignment if possible
        oldIndex = self.getCurrentConfigIndex(optID)
        if oldIndex is not None:
            if forceCode==0:
                return None
            if forceCode==1 and self.getCurrentConfigFlag(oldIndex)==1:
                return None
            removed.append(oldIndex)

        # Determine which fibers might collide with this assignment
        for fibIndex2,optID2 in self.iterateCurrentConfig():
            flag2 = self.getCurrentConfigFlag(fibIndex2)
            if optID2 is None or optID2==optID or fibIndex2==fibIndex or flag2==2:
                continue
            collide = self.checkCollision(fibIndex,optID,fibIndex2,optID2)
            if collide:
                if forceCode==0 or (forceCode==1 and flag2==True):
                    return None
                removed.append(fibIndex2)
        # Check if we drop below the FOPs limit
        if not self.INITIALIZING:
            NFOPS = self.NFOPS
            for r in removed:
                if r in self.FOPSindex:
                    NFOPS -= 1
            if NFOPS<self.MINFOPS:
                return None
        if isFOP and oldID is None:
            self.NFOPS += 1
        flag = 1 if forceCode==2 else 0
        for r in removed:
            if r in self.FOPSindex:
                self.NFOPS -= 1
            self.updateCurrentConfig(r,None,0.,False)
        self.updateCurrentConfig(fibIndex,optID,self.weights[optID],flag)
        return removed

    def selectObjectForFiber(self,fibIndex):
        # Always select the best possible fiber
        for optID in self.objList[fibIndex]:  
            if self.addObjectToConfiguration(fibIndex,optID) is None:
                continue
            break

    def annealingStep(self,iteration):
        from math import log

        T = (self.T1*(1-iteration/self.MAX)**self.nonlin)+self.T0

        originalConfig = self.copyCurrentConfig()
        tmpNFOPS = self.NFOPS
        # Draw the fiber to assign
        fibIndex = random.choice([index for index,flag in self.iterateCurrentFlags() if flag!=1])
        # Sometimes a fiber won't have any objects associated with it...
        if len(self.objList[fibIndex])==0:
            return
        # Draw the object to assign the fiber to; weight objects based upon
        #  their provided weights
        optID = random.choices(self.objList[fibIndex],self.objListWeights[fibIndex])[0]
        removed = self.addObjectToConfiguration(fibIndex,optID,forceCode=1)
        if removed is None:
            # If removed is none we've collided with a manually placed fiber
            self.restoreCurrentConfig(originalConfig)
            self.NFOPS = tmpNFOPS
            # We've collided with a manually placed fiber
            return
        for r in removed:
            self.selectObjectForFiber(r)

        ratio = self.currentConfig.score-originalConfig.score#score-newScore#sum(self.selectedWeight)-sum(tmpWeights)
        if ratio>=0 or ratio/T>log(random.random()):
            if self.currentConfig.score>self.bestConfig.score:
                self.bestConfig = self.copyCurrentConfig()
        else: # The move was *not* selected, so return to original state
            self.restoreCurrentConfig(originalConfig)
            self.NFOPS = tmpNFOPS

    def optimize(self):
        worker = Worker(self.doOptimize)
        from .progressbar import ProgressWindow
        myWindow = ProgressWindow(self,True)
        myWindow.setTitle("Optimizing")
        self.updateOptProgressSignal.connect(myWindow.updateProgress)
        self.updateScoreSignal.connect(myWindow.updateScoreLabel)
        self.threadPool.start(worker)
        myWindow.exec_()
        self.updateOptProgressSignal.disconnect(myWindow.updateProgress)
        self.updateScoreSignal.disconnect(myWindow.updateScoreLabel)
        time.sleep(0.1)
        self.showSelected()#self.selectedID)

    def doOptimize(self,nsteps=20000):
        # First reset all of the objects except manually selected fibers
        self.bestConfig = self.copyCurrentConfig()

        self.NFOPS = 0
        for index,flag in self.iterateCurrentFlags():
            if not flag:
                self.updateCurrentConfig(index,None,0.,False)
            elif index in self.FOPSindex:
                self.NFOPS += 1
        # Now add objects
        self.INITIALIZING = True
        # Start with FOPs
        for index in self.FOPSindex:
            if self.getCurrentConfigID(index) is None:
                self.selectObjectForFiber(index)
        for index,objid in self.iterateCurrentConfig():
            if objid is None:
                self.selectObjectForFiber(index)
        self.INITIALIZING = False
        if self.NFOPS<self.MINFOPS:
            self.printError("Not enough FOPs stars available to create a configuration.")
            self.restoreCurrentConfig(self.bestConfig)
            self.updateOptProgressSignal.emit(100)
            return

        self.T1 = 50.
        self.T0 = 0.
        self.MAX = nsteps
        self.nonlin = 2.

        NTOT = self.MAX*1.5
        NCOUNT = 0
        PCENT = [0,10,20,30,40,50,60,70,80,90]
        tlast = time.time()
        for i in range(self.MAX):
            NCOUNT += 1
            P = int(100*NCOUNT/NTOT)
            if P>=PCENT[0]:
                self.updateOptProgressSignal.emit(int(100*NCOUNT/NTOT))
                del PCENT[0]
            self.annealingStep(i)
            tnow = time.time()
            if tnow-tlast>0.1:
                tlast = tnow
                self.updateScoreSignal.emit(int(self.currentConfig.score))

        self.T1 = 100
        self.T0 = 50
        self.nonlin = 4

        tlast = time.time()
        for i in range(self.MAX//2,self.MAX):
            NCOUNT += 1
            P = int(100*NCOUNT/NTOT)
            if len(PCENT) and P>=PCENT[0]:
                self.updateOptProgressSignal.emit(int(100*NCOUNT/NTOT))
                del PCENT[0]
            self.annealingStep(i)
            tnow = time.time()
            if tnow-tlast>0.1:
                tlast = tnow
                self.updateScoreSignal.emit(int(self.currentConfig.score))
        self.restoreCurrentConfig(self.bestConfig)
        self.updateOptProgressSignal.emit(100)

    def showSelected(self):
        selected = self.currentConfig.IDs
        self.updateBestConfig()
        # Remove all assignments to objects
        for objid in self.catalog.keys():
            self.catalog[objid]["fibid"] = None
            self.catalog[objid]["slitid"] = None

        for fibID in self.fibers:
            sfibID = str(fibID)
            self.FiberDB[sfibID]["object"] = -1
            self.FiberDB[sfibID]["x"] = self.FiberDB[sfibID]["xpark"]
            self.FiberDB[sfibID]["y"] = self.FiberDB[sfibID]["ypark"]
            self.FiberDB[sfibID]["parked"] = True
            self.FiberDB[sfibID]["queued"] = False
        self.updateFiberStatus(self.FiberDB)

        for fibIndex,optID in enumerate(selected):
            if optID is None:
                continue
            fibID = self.fibers[fibIndex]
            objID = self.idmap[optID]
            sfibID = str(fibID)
            self.FiberDB[sfibID]["object"] = objID
            self.FiberDB[sfibID]["x"] = self.catalog[objID]["x"]
            self.FiberDB[sfibID]["y"] = self.catalog[objID]["y"]
            self.FiberDB[sfibID]["queued"] = self.getCurrentConfigFlag(fibIndex)==1#self.selectedFlag[fibIndex]==1
            self.FiberDB[sfibID]["parked"] = False
            self.catalog[objID]["fibid"] = fibID
            self.catalog[objID]["slitid"] = int(self.FiberDB[sfibID]["slit"])

        self.updateFiberStatus(self.FiberDB)
        self.updateFiberTable(self.catalog)


