import sys,os
try:
    from importlib import resources as importlib_resources
except ImportError:
    import importlib_resources


from PyQt6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QMessageBox, QTableWidgetItem,
QWidget,QStyleFactory,QHeaderView)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal,pyqtSlot,Qt,QEvent,QThreadPool,QTimer
from PyQt6.uic import loadUi

from platformdirs import user_cache_dir

from .FiberPlacement import Ui_MainWindow
from .fiberdisplay import FiberDisplayManager
from .inputcatalog import CatalogManager
from .updatehandler import UpdateHandler
from .fiberdisplay import FiberDisplayManager
from .fiberinitializer import FiberInitializer
from .astrometry import Astrometry
from .collision import CollisionMatrix
from .configuration import Configuration
from .placer import FiberPlacer



class Window(QMainWindow, Ui_MainWindow,CatalogManager,UpdateHandler,FiberInitializer,Astrometry,CollisionMatrix,Configuration,FiberPlacer):

    def __init__(self,parent=None):
        super().__init__(parent)
        self.threadPool = QThreadPool()

        self.setupUi(self)
        self.setWindowFlag(Qt.WindowType.WindowSystemMenuHint|Qt.WindowType.WindowCloseButtonHint, True)
        self.setWindowTitle("NeWHydra")

        # Make the cache if necessary
        self.cachedir = user_cache_dir("newhydra")
        os.makedirs(self.cachedir,exist_ok=True)

        self.fieldinfo.setStyleSheet("background-color: rgba(255,255,255,0.5); border-radius: 4px;")
        self.fieldname_label.setStyleSheet("background-color: rgba(255,255,255,0.5)")
        self.coords.setStyleSheet("background-color: rgba(255,255,255,0.4); border-radius: 4px;")
        self.showmarkers.setStyleSheet("background-color: rgba(255,255,255,0.4); border-radius: 4px;")
        self.fieldinfo.hide()
        self.showmarkers.hide()

        self.fiberCountTable.setSpan(0,0,1,2)
        self.fiberCountTable.setStyleSheet("""
        QTableWidget { border: 0px solid black;
                        background: rgba(255,255,255,0.6)}
        QTableWidget::item { border: 1px solid black; }
        """)
        self.fiberCountTable.setColumnWidth(0,45)
        self.fiberCountTable.setColumnWidth(1,35)
        self.fiberCountTable.hide()


        self.markersLayout.addStretch()
        self.showfops_cbox.setStyleSheet("background-color: rgba(255,255,255,0)")
        self.showtargets_cbox.setStyleSheet("background-color: rgba(255,255,255,0)")
        self.showskys_cbox.setStyleSheet("background-color: rgba(255,255,255,0)")
        self.ps1image_cbox.setStyleSheet("background-color: rgba(255,255,255,0)")
        # Disable the PS1 image checkbox until an image is loaded
        self.ps1image_cbox.setEnabled(False)

        self.xcoord_label.setIndent(3)
        self.ycoord_label.setIndent(3)

        self.printMessageSignal.connect(self.printMessage)
        self.fiberSignal.connect(self.updateFiberStatus)
        self.targetSignal.connect(self.updateFieldInfo)
        self.imageSignal.connect(self.setImageDirect)

        configFileData = importlib_resources.files('newhydra').joinpath('data/hydraConfig.json')
        self.HydraConfig = eval(configFileData.read_text())
        self.sitePars = self.HydraConfig["WIYN"]
        self.setButtons()

        self.getConcentricities()
        self.DisplayManager = FiberDisplayManager(self)

        self.DisplayManager.updateFiberDB(self.FiberDB)

        self.setupTable()
        self.loadField_btn.clicked.connect(self.loadFieldFile)

        self.optimize_btn.clicked.connect(self.optimize)
        self.makeSkies_btn.clicked.connect(self.removeLowestWeightedFibers)

        self.saveConfig_btn.clicked.connect(self.outputCatalog)

        self.resetCurrentConfig()
        self.reset_btn.clicked.connect(self.resetPopup)

        self.showUnassigned_btn.clicked.connect(self.DisplayManager.startUnassignedBlink)

        self.messageBox.setStyleSheet("font: 9pt 'Courier';")


        # We place the prompt() call behind a QTimer to give the
        #  GUI a chance to come up before the OpenFile dialog
        QTimer.singleShot(50,self.prompt)

    def prompt(self):
        if len(sys.argv)>1:
            self.loadFieldFile(filename=sys.argv[1])
        else:
            self.loadFieldFile()

    def changeEvent(self,event):
        # Prevent window from moving to upper-left corner on maximize event
        if event.type()==QEvent.Type.WindowStateChange:
            if self.windowState()==Qt.WindowState.WindowMaximized:
                self.showNormal()
    
    def assignFiber(self,obj=None,fib=None,remove=False):
        from .popupWindow import AssignFiberPopup,YesNoPopup
        if obj is not None and type(obj)==int:
            obj = str(obj)
        if fib is not None and type(fib)==int:
            fib = str(fib)
        if fib is not None and obj is not None and not remove:
            popup = YesNoPopup(self,"Do you want to assign Fiber %s to Object %s?"%(fib,obj))
        elif remove and (fib is not None or obj is not None):
            if obj is not None:
                popup = YesNoPopup(self,"Do you want to remove the fiber assignment from Object %s?"%(obj.strip()))
                fib = "-1"
            else:
                popup = YesNoPopup(self,"Do you want to remove the object assigned to Fiber %s?"%(fib))
                obj = "-1"
        else:
            popup = AssignFiberPopup(self,obj=obj,fib=fib)
        if popup.exec_():
            if fib is None or obj is None:
                obj,fib = popup.getData()
            fib = fib.strip()
            obj = obj.strip()
            return self.updateFiberAssignment(int(obj),int(fib),remove)

    def updateFiberAssignment(self,objID,fibID,remove=False,forceCode=2,doShow=True):
        fibIndex = None
        if objID==-1:
            fibIndex = self.fibers.index(fibID)
            remove = True
        elif fibID==-1:
            optID = self.idmap.index(objID)
            fibIndex = self.getCurrentConfigIndex(optID)
            remove = True
        if remove:
            if fibIndex is None:
                fibIndex = self.fibers.index(fibID)
            self.updateCurrentConfig(fibIndex,None,0,False)
        else:
            optID = self.idmap.index(objID)
            fibIndex = self.fibers.index(fibID)
            if optID in self.objList[fibIndex]:
                result = self.addObjectToConfiguration(fibIndex,optID,forceCode=forceCode)
                if result is None:
                    self.printError("Fiber {} could not be assigned.".format(fibID))
                    return False
            else:
                self.printError("Fiber {} could not be assigned.".format(fibID))
                return False
        if doShow:
            self.showSelected()
        return True

    def removeLowestWeightedFibers(self):
        from .popupWindow import HowManyFibersPopup

        fibs,wts = [],[]
        for index,optID in self.iterateCurrentConfig():
            if optID is None or self.getCurrentConfigFlag(index) or index in self.FOPSindex:
                continue
            fibs.append(index)
            wts.append(self.getCurrentConfigWeight(index))
        if not fibs:
            return
        args = sorted(range(len(wts)),key=wts.__getitem__,reverse=False)
        popup = HowManyFibersPopup(self,len(fibs))
        if popup.exec_():
            N = popup.getData()
            for index in args[:N]:
                fibIndex = fibs[index]
                self.updateCurrentConfig(fibIndex,None,0,False)
            self.showSelected()

    def resetPopup(self):
        from .popupWindow import YesNoPopup
        popup = YesNoPopup(self,"Do you also want to reset\nmanually placed fibers?")
        answer = popup.exec_()
        if answer is not None:
            self.resetCurrentConfig(removeManual=answer)
            self.showSelected()

    def str2deg(self,instr):
        instr = instr.replace(":"," ")
        d,m,s = instr.split()
        sign = -1 if d[0]=='-' else 1
        return sign*(abs(float(d))+float(m)/60+float(s)/3600)

    def ra2str(self,ra,sep=' '):
        H = ra/15.
        h = int(H)
        m = int((H-h)*60)
        s = ((H-h)*60-m)*60
        return "%02d%s%02d%s%06.3f"%(h,sep,m,sep,s)

    def dec2str(self,dec,sep=' '):
        sign = "+" if dec>=0 else "-"
        dec = abs(dec)
        d = int(dec)
        m = int((dec-d)*60)
        s = ((dec-d)*60-m)*60
        return "%s%02d%s%02d%s%05.2f"%(sign,d,sep,m,sep,s)

    @pyqtSlot(str)
    def printMessage(self,*kargs):
        message = " ".join(kargs)
        print(message)
        self.messageBox.append("> "+message)

    def printError(self,*kargs):
        message = " ".join(kargs)
        print(message)
        message = "<font color='red'>%s</font>"%(message)
        self.messageBox.append("> "+message)

    @pyqtSlot(object,float)
    def setImageDirect(self,img,angle):
        self.DisplayManager.plate.setPS1ImageDirect(img,angle)

def main():
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
