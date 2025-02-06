from PyQt6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsEllipseItem, \
        QGraphicsLineItem,QMenu,QGraphicsPathItem,QGraphicsItem,\
        QGraphicsPixmapItem
from PyQt6.QtGui import QPainter,QBrush,QPen,QColor,QPainterPath,QPixmap,QImage,QNativeGestureEvent
from PyQt6.QtCore import Qt,QTimer,QRectF,pyqtSlot
from .displayobjects import Compass,FieldCompass,Fiber,StarMarker,SquareMarker,CircleMarker

class FiberDisplayView(QGraphicsView):
    """
    We subclass QGraphicsView to allow panning/zooming. We also override the
      default panning behavior of always having a drag-hand cursor.
    """
    def __init__(self,parent):
        super(QGraphicsView,self).__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setMouseTracking(True)
        self.cursor = Qt.CursorShape.ArrowCursor
        self.currentScale = 1.
        self.currentOffset = None
        self.main = parent.parent()

    def viewportEvent(self,event):
        if type(event)==QNativeGestureEvent and event.gestureType()==Qt.NativeGestureType.ZoomNativeGesture:
            self.wheelEvent(event)
            return True
        return super().viewportEvent(event)

    # Zoom with the mouse wheel
    def wheelEvent(self,event):
        zoom = 1.2
        if type(event)==QNativeGestureEvent:
            if event.value()<0:
                zoom = 1/zoom
        elif event.angleDelta().y()<0:
            zoom = 1/zoom
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.currentScale *= zoom
        self.scale(zoom,zoom)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    # Use a normal arrow cursor instead of the drag hand
    def enterEvent(self,event):
        super().enterEvent(event)
        self.viewport().setCursor(self.cursor)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        self.viewport().setCursor(self.cursor)


class FiberDisplayScene(QGraphicsScene):
    """
    We subclass QGraphicsScene to always show the mouse position in the
      coordinates label.
    """
    def __init__(self,width,height,manager):
        super(QGraphicsScene, self).__init__(0,0,width,height)
        self.manager = manager
        self.main = manager.main

    # Update the coordinates
    def mouseMoveEvent(self,event):
        super().mouseMoveEvent(event)
        x = event.scenePos().x()
        y = event.scenePos().y()
        x,y = self.manager.gui2hydra(x,y)
        self.main.xcoord_label.setText('x=%4d'%(x))
        self.main.ycoord_label.setText('y=%4d'%(y))

class FocalPlate(QGraphicsEllipseItem):
    """
    FocalPlate graphically represents the Hydra plate, but also shows the
      PS1 image of the field and implements a `move here/assign target'
      context menu.
    """
    def __init__(self,manager,x0,y0,dx,dy):
        super(QGraphicsEllipseItem,self).__init__(x0,y0,dx,dy)
        self.manager = manager
        self.showPS1 = False
        self.angle = 0.

    def showImage(self,flag):
        self.showPS1 = flag
        self.update()

    def setPS1Image(self,img):
        import base64
        self.pixmap = QPixmap()
        data = base64.b64decode(img)
        res = self.pixmap.loadFromData(data)
        self.manager.main.ps1image_cbox.setEnabled(res)
        self.update()

    def setPS1ImageDirect(self,img,angle):
        #self.pixmap = QPixmap()
        #img = img.convert("RGB")
        self.angle = angle
        data = img.tobytes("raw","RGB")
        qim = QImage(data,img.size[0],img.size[1],QImage.Format.Format_RGB888)
        self.pixmap = QPixmap.fromImage(qim)
        self.manager.main.ps1image_cbox.setEnabled(True)
        self.manager.main.ps1image_cbox.setChecked(True)
        self.update()

    def contextMenuEvent(self,event):
        menu = QMenu()
        addskyposition = menu.addAction("Add Sky Position")
        addskyposition.triggered.connect(lambda: self._addSkyPosition(event.scenePos()))
        menu.exec(event.screenPos())

    def _addSkyPosition(self,pos):
        """
        Get the RA/Dec at the plate position and ask to assign a sky position.
        """
        X = pos.x()
        Y = pos.y()
        xx,yy = self.manager.gui2hydra(X,Y)
        ra,dec = self.manager.main.plateToSky(xx,yy)
        self.manager.main.addTarget(ra,dec)

    def paint(self,*args):
        super().paint(*args)
        if self.showPS1:
            args[0].setClipPath(self.shape())
            args[0].rotate(self.angle)
            args[0].drawPixmap(self.rect(),self.pixmap,QRectF(self.pixmap.rect()))

class FiberDisplayManager:
    PLATESIZE = 420

    PlateBrush = QBrush(QColor(192,192,192))
    BlackBrush = QBrush(Qt.GlobalColor.black)

    def __init__(self,parent):#,fiberInitDB):
        self.main = parent
        self.initialized = False

        self.FiberDB = None
        self.TargetDB = None
        self.tracking = False

        self.HYDRAPLATE = parent.HydraConfig["PLATE"]
        self.SCALE = self.PLATESIZE/2/self.HYDRAPLATE
        self.FIBERHALFWIDTH = parent.HydraConfig["FIBERTUBE_HALFDIAMETER"]*self.SCALE
        self.BUTTONSIZE = parent.HydraConfig["FIBERBUTTON_RADIUS"]*2*self.SCALE
        self.FIBERSEGMENTS = parent.HydraConfig["FIBERTUBE_SEGMENTS"]
        from math import pi
        self.MAXBEND = parent.HydraConfig["MAXANGLE"]*180/pi
        self.MAXEXTEND = parent.HydraConfig["MAXEXTEND"]*self.SCALE
        self.NFIBERS = parent.HydraConfig["NFIBERS"]

    def init(self,fiberInitDB):
        self.initialized = True
        self.Fibers = {}
        self.Targets = []

        self.blinkingMarker = None

        size = self.main.fiberdisplay.size()
        width,height = size.width()-4,size.height()-4
        self.x0 = width/2
        self.y0 = height/2

        self.fiberScene = FiberDisplayScene(width,height,self)
        self.main.fiberdisplay.setScene(self.fiberScene)

        # First add the compasses
        self.compass = FieldCompass(self.x0,self.y0)
        self.compass.setBrush(QBrush(self.BlackBrush))
        self.compass.setPen(QPen(self.BlackBrush,0.3))
        self.compass.setVisible(False)
        self.fiberScene.addItem(self.compass)

        #self.rotator = Compass(self.x0,self.y0)
        #self.rotator.setBrush(QBrush(QColor(190,74,68)))
        #self.rotator.setPen(QPen(self.BlackBrush,0))
        #self.fiberScene.addItem(self.rotator)

        PS = self.PLATESIZE
        self.plate = FocalPlate(self,-PS/2,-PS/2,PS,PS)
        self.plate.setPos(self.x0,self.y0)

        self.plate.setBrush(self.PlateBrush)
        self.plate.setPen(QPen(self.BlackBrush,2))

        self.fiberScene.addItem(self.plate)

        # Now add the fibers
        self.createFibers(fiberInitDB)

        # Connect toggles to show/hide markers and PS1 image
        self.main.showtargets_cbox.stateChanged.connect(self.targetsShowHide)
        self.main.showfops_cbox.stateChanged.connect(self.fopsShowHide)
        self.main.showskys_cbox.stateChanged.connect(self.skysShowHide)
        self.main.ps1image_cbox.stateChanged.connect(self.imageShowHide)

        self.BlinkTimer = QTimer(self.main)
        self.BlinkTimer.timeout.connect(self.blinkMarker)


    def setImage(self,img):
        self.plate.setPS1Image(img)

    #def setImageDirect(self,data):
    #    img,angle = data
    #    self.plate.setPS1ImageDirect(img,angle)

    def createFibers(self,fiberDB):
        for fibid,data in fiberDB.items():
            fibid = int(fibid)
            self.Fibers[fibid] = Fiber(data,self)

    def hydra2gui(self,x,y):
        return x*self.SCALE+self.x0,-y*self.SCALE+self.y0

    def gui2hydra(self,x,y):
        return (x-self.x0)/self.SCALE,-(y-self.y0)/self.SCALE

    def startUnassignedBlink(self,state,nblinks=15):
        self.BlinkTimer.stop()
        if self.blinkingMarker is not None:
            for M in self.blinkingMarker:
                M.setScale(1.)
        self.blinkingMarker = []
        for fibid,fiber in self.Fibers.items():
            if fiber.active and fiber.objid<0:
                self.blinkingMarker.append(fiber.plotButton)
        if len(self.blinkingMarker)>0:
            self.nMarkerBlinks = nblinks
            for M in self.blinkingMarker:
                M.setScale(2)
            self.BlinkTimer.start(150)

    def startMarkerBlink(self,state=None,nblinks=15):
        self.BlinkTimer.stop()
        if self.blinkingMarker is not None:
            for M in self.blinkingMarker:
                M.setScale(1)
        self.blinkingMarker = None
        for M in self.Targets:
            if M.objid==state:
                self.blinkingMarker = [M]
                break
        if self.blinkingMarker is None:
            return
        self.nMarkerBlinks = nblinks
        self.main.fiberdisplay.centerOn(self.blinkingMarker[0].pos())
        self.blinkingMarker[0].setScale(2)
        self.BlinkTimer.start(150)

    def blinkMarker(self):
        self.nMarkerBlinks -= 1
        if self.nMarkerBlinks>0:
            for M in self.blinkingMarker:
                scale = M.scale()
                if scale==1:
                    M.setScale(2)
                else:
                    M.setScale(1)
        else:
            self.BlinkTimer.stop()
            for M in self.blinkingMarker:
                M.setScale(1)

    def updateRotator(self,angle):
        self.rotator.rotate(angle)

    def updateSymbols(self,doUpdate):
        if doUpdate:
            self.updateFibers()
            if self.TargetDB is not None:
                self.updateTargets()

    def updateFiberDB(self,db):
        if not self.initialized:
            self.init(db)
        else:
            self.FiberDB = db
        self.updateFibers()

    def updateTargetDB(self,db,angle=None):
        self.TargetDB = db
        if angle is not None:
            self.compass.setVisible(True)
            self.compass.rotate(angle)
        self.updateTargets()

    def updateFibers(self):
        if self.FiberDB is None:
            return
        for fibid,data in self.FiberDB.items():
            fibid = int(fibid)
            self.Fibers[fibid].stowed = data["stowed"]
            self.Fibers[fibid].parked = data["parked"]
            # NB: This could end up drawing the fibers multiple times
            if data["active"]!=self.Fibers[fibid].active:
                self.Fibers[fibid].setActiveStatus(data["active"])
            if data["queued"]!=self.Fibers[fibid].queued:
                self.Fibers[fibid].setQueueStatus(data["queued"])
            if data["object"]!=self.Fibers[fibid].objid:
                self.Fibers[fibid].setObject(data["object"])
            x,y = self.hydra2gui(data['x'],data['y'])
            if self.Fibers[fibid].x!=x or self.Fibers[fibid].y!=y:
                self.Fibers[fibid].updateXY(x,y)

    def updateTargets(self):
        # Remove the old targets
        while len(self.Targets):
            self.fiberScene.removeItem(self.Targets.pop())
        # Add the new targets
        if self.TargetDB is None:
            return
        for objid,data in self.TargetDB.items():
            x,y = self.hydra2gui(data['x'],data['y'])
            if data["type"]=='F':
                M = StarMarker(5,objid)
            elif data["type"]=='S':
                M = CircleMarker(3,objid)
            else:
                M = SquareMarker(3,objid)
            M.setPos(x,y)
            if self.plate.showPS1:
                M.setOpacity(0.5)
            if data["fibid"] is not None:
                M.setToolTip("Objid: %s (Fiber %s)\n%s"%(objid,data["fibid"],data["name"].strip()))
            else:
                M.setToolTip("Objid: %s\n%s"%(objid,data["name"].strip()))
            self.Targets.append(M)
            self.fiberScene.addItem(self.Targets[-1])
        self.targetsShowHide()
        self.fopsShowHide()
        self.skysShowHide()
        self.TargetDB = None

    def doAcquire(self): # OBSOLETE
        cboxes = [self.main.showtargets_cbox,
                  self.main.showfops_cbox,
                  self.main.showskys_cbox]
        if self.main.hideFibersAndObjects.isChecked():
            for cbox in cboxes:
                cbox.setEnabled(False)
            for target in self.Targets:
                target.hide()
            for fiber in self.Fibers:
                if self.Fibers[fiber].cable!='F':
                    self.Fibers[fiber].setVisible(False)
        else:
            for cbox in cboxes:
                cbox.setEnabled(True)
            for target in self.Targets:
                target.show()
            for fiber in self.Fibers:
                self.Fibers[fiber].setVisible(True)


    def targetsShowHide(self):
        self.markerShowHide(self.main.showtargets_cbox.isChecked(),SquareMarker)

    def fopsShowHide(self):
        self.markerShowHide(self.main.showfops_cbox.isChecked(),StarMarker)

    def skysShowHide(self):
        self.markerShowHide(self.main.showskys_cbox.isChecked(),CircleMarker)

    def markerShowHide(self,show,marker):
        for target in self.Targets:
            if type(target)==marker:
                if show:
                    target.show()
                else:
                    target.hide()

    def imageShowHide(self):
        state = self.main.ps1image_cbox.isChecked()
        self.plate.showImage(state)
        opacity = 0.5 if state else 1
        for target in self.Targets:
            target.setOpacity(opacity)
