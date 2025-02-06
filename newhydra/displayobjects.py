from PyQt6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsEllipseItem, \
        QGraphicsLineItem,QGraphicsPolygonItem,QGraphicsRectItem,QMenu, \
        QGraphicsPathItem
from PyQt6.QtGui import QPainter,QColor,QBrush,QPen,QPolygonF,QPainterPath, \
        QTransform,QPainterPathStroker,QFont
from PyQt6.QtCore import Qt,QPointF,QPoint,QRectF


"""
Classes for display objects, e.g., fibers, compasses, and target markers.
"""

# This needs to be accounted for when determining the button size (for
#  collision detection).
BUTTON_PEN_WIDTH = 0.5

BlueBrush = QBrush(Qt.GlobalColor.blue) # For blue fibers
RedBrush = QBrush(Qt.GlobalColor.red) # For red fibers and illegal fibers
GrayBrush = QBrush(Qt.GlobalColor.lightGray) # For inactive fibers
YellowBrush = QBrush(Qt.GlobalColor.yellow) # For FOPS and stars
BlackBrush = QBrush(Qt.GlobalColor.black) # For active fibers and default pen
DarkRedBrush = QBrush(Qt.GlobalColor.darkRed) # For illegal fibers
ScienceBrush = QBrush(QColor(200,255,200)) # For science objects
SkyBrush = QBrush(QColor(200,200,255)) # For sky objects


Pen = QPen(BlackBrush,0.3) # Default pen
AssignedPen = QPen(RedBrush,0.3) # Border of assigned targets
PlacedPen = QPen(QBrush(Qt.GlobalColor.darkGreen),0.3) # Border of placed targets

BlackButtonPen = QPen(Qt.GlobalColor.black,BUTTON_PEN_WIDTH) # Active buttons
GrayButtonPen = QPen(Qt.GlobalColor.gray,BUTTON_PEN_WIDTH) # Inactive buttons

nullPen = QPen(Qt.GlobalColor.black,0.) # Zero-width pen


class Compass(QGraphicsPathItem):
    """
    Rotator compass and base class for FieldCompass
    """
    def __init__(self,x0,y0):
        super().__init__()
        self.x0 = x0
        self.y0 = y0

        self.width = 2
        self.headwidth = 4
        self.height = 216
        self.headheight = 10
        self.rotation = 0
        self.drawCompass()

    def drawCompass(self):
        """
        The compass is drawn as a filled line path, with points empirically
          chosen.
        """
        path = QPainterPath()
        path.moveTo(self.width/2,-self.width/2)
        path.lineTo(self.width/2,self.height+self.headheight)
        path.lineTo(-self.headwidth,self.height)
        path.lineTo(-self.width/2,self.height)
        path.lineTo(-self.width/2,self.width/2)
        path.lineTo(-self.height,self.width/2)
        path.lineTo(-self.height,self.headwidth)
        path.lineTo(-self.height-self.headheight,-self.width/2)
        path.lineTo(self.width/2,-self.width/2)

        path.translate(self.x0,self.y0)

        self.path = path
        self.setPath(self.path)
        self.setTransformOriginPoint(self.x0,self.y0)

    def rotate(self,rotation):
        self.rotation = -rotation
        self.setRotation(self.rotation)
        self.update()

class FieldCompass(Compass):
    """
    Compass with N,E annotations
    """
    def __init__(self,x0,y0):
        super().__init__(x0,y0)
        self.width = 4
        self.headwidth = 6
        self.headheight = 15
        height = 215
        self.drawCompass()

    def paint(self,*args):
        """
        We override the paint() method to append N,E labels
        """
        super().paint(*args)
        # Add N,E labels to the field compass
        args[0].save()
        transform = QTransform()
        transform.translate(self.x0,self.y0)
        transform.rotate(180)
        args[0].setTransform(transform,True)
        font = QFont("Helvetica",8)
        font.setBold(True)
        args[0].setFont(font)
        args[0].drawText(QPointF(self.width/2,-self.height-self.headheight/2),"N")
        args[0].drawText(QPointF(self.height+self.headheight/2,-self.width/2),"E")
        args[0].restore()


class Button(QGraphicsEllipseItem):
    """
    Fiber button; this is just the *button* (i.e., circle) part of the fiber.
      The button:
        - provides a context menu for assigning, parking, etc.
        - is the anchor for moving the fiber
    """
    def __init__(self,size,fiber):
        super(QGraphicsEllipseItem,self).__init__(-size/2,-size/2,size,size)
        self.fiber = fiber
        self.main = fiber.manager.main
        self.setToolTip("Fiber %s"%(fiber.fibid))
        self.startPos = None

    def contextMenuEvent(self,event):
        if self.fiber.active and not self.fiber.parked:
            fibid = self.fiber.fibid
            fibStr = '%d'%(fibid)

            menu = QMenu()
            menu.setTitle(fibStr)
            _ = menu.addSection("Fiber %s"%(fibStr))
            park = menu.addAction("Deassign")

            M = self.main
            park.triggered.connect(lambda: M.assignFiber(fib=fibid,remove=True))
            menu.exec(event.screenPos())

    def getNearestMarker(self):
        objs = self.collidingItems()
        if len(objs)==0:
            return None
        P = self.pos()
        match = None
        dist = 1e10
        for obj in objs:
            if type(obj) not in [SquareMarker,CircleMarker,StarMarker]:
                continue
            tmp = obj.pos()-P
            D = tmp.x()**2+tmp.y()**2
            if D<dist:
                match = obj
                dist = D
        return match

    def mousePressEvent(self,event):
        """
        #  We override to allow the button to be moved.
        #
        #  self.startPos not None signals that the button is being moved.
        """
        super().mousePressEvent(event)
        if self.startPos is None and self.fiber.active \
                and event.button()==Qt.MouseButton.LeftButton:
            self.startPos = self.pos()

    def mouseMoveEvent(self,event):
        super().mouseMoveEvent(event)
        if self.startPos is not None:
            P = self.pos()
            self.fiber.setFiber(P)

    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if self.startPos is None or event.button()!=Qt.MouseButton.LeftButton:
            return
        """
        # We check that the fiber has been moved to an OK location 
        """
        if self.fiber.psi<self.fiber.manager.MAXBEND and self.fiber.ext<self.fiber.manager.MAXEXTEND:
            match = self.getNearestMarker()
            if match is not None:
                if str(self.fiber.objid)!=match.objid:
                    self.fiber.setFiber(match.pos())
                    self.setPos(match.pos())
                    if self.fiber.psi<self.fiber.manager.MAXBEND and self.fiber.ext<self.fiber.manager.MAXEXTEND:
                        if self.main.assignFiber(fib=self.fiber.fibid,obj=match.objid):
                            self.startPos = None
                            return
        self.setPos(self.startPos)
        self.fiber.setFiber(self.startPos)
        self.startPos = None

class Fiber:
    """
    Fiber describes the full fiber object, including the button and the fiber
      tube. Note that the tube has two components, the visual component and
      a `shadow' component for collision detection consistent with the server.
    """
    def __init__(self,data,manager):
        from math import atan2
        self.manager = manager
        self.BUTTONSIZE = manager.BUTTONSIZE-BUTTON_PEN_WIDTH
        self.fibid = data["fiber"]
        self.x,self.y = manager.hydra2gui(data['x'],data['y'])
        self.xpivot,self.ypivot = manager.hydra2gui(data["xpivot"],data["ypivot"])
        self.pivotX = self.xpivot-self.manager.x0
        self.pivotY = self.ypivot-self.manager.y0
        self.pivotDistance = (self.pivotX**2+self.pivotY**2)**0.5
        self.theta = atan2(self.pivotY,self.pivotX)
        self.cable = data["cable"]
        self.status = data["status"]
        self.slit = data["slit"]
        self.active = data["active"]
        self.queued = data["queued"]
        self.parked = data["parked"]
        self.stowed = data["stowed"]
        self.objid = data["object"]
        self.legal = True

        # Valid FOPS are always active
        if self.cable=='F' and self.status=='A':
            self.active = True


        self.plotButton = Button(self.BUTTONSIZE,self)
        self.plotFiber = QGraphicsPathItem()
        if self.cable=='R':
            self.plotFiber.setPen(QPen(Qt.GlobalColor.red,0.))
        elif self.cable=='B':
            self.plotFiber.setPen(QPen(Qt.GlobalColor.blue,0.))
        elif self.cable=='F':
            self.plotFiber.setPen(QPen(Qt.GlobalColor.yellow,0.))
        else:
            self.plotFiber.setPen(QPen(Qt.GlobalColor.black,0.))

        self.plotFiber.setOpacity(0.7)
        self.collisionFiber = QGraphicsPolygonItem()
        self.collisionFiber.setPen(nullPen)
        self.collisionFiber.setOpacity(0.)
        self.collisionFiber.fibid = self.fibid
        self.setFiber()
        self.setObject(data["object"])

        self.manager.fiberScene.addItem(self.plotFiber)
        self.manager.fiberScene.addItem(self.plotButton)
        self.manager.fiberScene.addItem(self.collisionFiber)
        self.drawFiber()

    def setObject(self,objid):
        """
        Show the object ID if the fiber is assigned to an object.
        """
        self.objid = objid
        if objid>=0:
            self.plotFiber.setToolTip("Fiber %s\n(Object %d)"%(self.fibid,objid))
        else:
            self.plotFiber.setToolTip("Fiber %s"%(self.fibid))

    def setVisible(self,state):
        """
        Sync the visibility of the fibertube and button.
        """
        if state:
            self.plotFiber.show()
            self.plotButton.show()
        else:
            self.plotFiber.hide()
            self.plotButton.hide()

    def getFiberGeometry(self,pos=None):
        """
        We plot the fibers using the same parametric description as used by
        the fiber collision algorithm, that is:
            y = 0.5*x^3 - 1.5*x + 1
        We then scale the points to the actual fiber-position geometry,
        calculating the deflection from the radial line and the extent
        along that line. Finally, we rotate to the correct angle.
        """
        from math import atan2,sin,cos,pi
        # These are empirically determined to be the Bezier control points
        #   needed to mimic the polynomial on [0,1]: y = 0.5*x^3-1.5*x+1
        xcontrol = [0., 1./3, 2./3., 1.]
        ycontrol = [0., 0., 0.5,1.]

        if pos is None:
            xin = self.x
            yin = self.y
        else:
            xin = pos.x()
            yin = pos.y()

        theta = self.theta
        P = self.pivotDistance

        X = xin-self.manager.x0
        Y = yin-self.manager.y0
        D = (X**2+Y**2)**0.5

        phi = atan2(Y,X)-theta

        defl = D*sin(phi)
        Dproj = D*cos(phi)
        ext = P-Dproj
        self.psi = abs(atan2(defl,ext))*180/pi
        self.ext = ext

        x = [P-xc*ext for xc in xcontrol]
        y = [yc*defl for yc in ycontrol]
        xrot = [0.,0.,0.,0.]
        yrot = [0.,0.,0.,0.]
        s = sin(theta)
        c = cos(theta)

        for i in range(len(x)):
            xrot[i] = c*x[i]-s*y[i]+self.manager.x0
            yrot[i] = s*x[i]+c*y[i]+self.manager.y0

        eps = self.manager.FIBERSEGMENTS[1:]
        points = [0]*(len(eps)+1)*2
        lastx,lasty = X,Y#xin,yin
        for i in range(len(eps)):
            deflN = defl*(0.5*eps[i]**3-1.5*eps[i]+1)
            dN = Dproj+ext*eps[i]
            rn = (deflN**2+dN**2)**0.5
            phiN = atan2(deflN,dN)

            xp = rn*cos(theta+phiN)
            yp = rn*sin(theta+phiN)

            dx = xp-lastx
            dy = yp-lasty
            dnorm = (dx*dx+dy*dy)**0.5

            vx = -self.manager.FIBERHALFWIDTH*dy/dnorm
            vy = self.manager.FIBERHALFWIDTH*dx/dnorm
            points[i] = QPointF(lastx+vx,lasty+vy)
            
            vx *= -1
            vy *= -1
            points[9-i] = QPointF(lastx+vx,lasty+vy)
            lastx,lasty = xp,yp
        points[5] = QPointF(lastx+vx,lasty+vy)
        points[4] = QPointF(lastx-vx,lasty-vy)
        for i in range(len(points)):
            points[i].setX(points[i].x()+self.manager.x0)
            points[i].setY(points[i].y()+self.manager.y0)

        return xrot,yrot,vx,vy,points

    def setFiber(self,pos=None):
        X,Y,vx,vy,polyPoints = self.getFiberGeometry(pos)

        path = QPainterPath()
        X1 = [_+vx for _ in X]
        Y1 = [_+vy for _ in Y]
        path.moveTo(X1[0],Y1[0])
        path.cubicTo(X1[1],Y1[1],X1[2],Y1[2],X1[3],Y1[3])

        X2 = [_-vx for _ in X][::-1]
        Y2 = [_-vy for _ in Y][::-1]
        path.lineTo(X2[0],Y2[0])
        path.cubicTo(X2[1],Y2[1],X2[2],Y2[2],X2[3],Y2[3])

        self.plotFiber.setPath(path)
        M = self.collisionFiber
        self.collisionFiber.setPolygon(QPolygonF(polyPoints))

        if self.active:
            self.plotFiber.setBrush(BlackBrush)
        else:
            self.plotFiber.setBrush(GrayBrush)
        if self.queued:
            if self.cable=='R':
                self.plotFiber.setBrush(QColor("orange"))
            else:
                self.plotFiber.setBrush(Qt.GlobalColor.cyan)

        #
        # Simple tests of placing validity
        #
        self.legal = True
        if self.psi>self.manager.MAXBEND or self.ext>self.manager.MAXEXTEND:
            self.legal = False
            self.plotFiber.setBrush(RedBrush)

        #
        # Check that the fiber and button don't collide with other fibers or
        #  buttons (other than their own)
        lo = (self.fibid-1)%self.manager.NFIBERS
        hi = (self.fibid+1)%self.manager.NFIBERS
        if self.legal:
            for obj in self.collisionFiber.collidingItems():
                if obj==self.plotButton:
                    continue
                if not self.legalParkTest(obj,lo,hi):
                    self.legal = False
                    break
                #if type(obj) in [Button,QGraphicsPolygonItem]:
                #    self.legal = False
        if self.legal:
            for obj in self.plotButton.collidingItems():
                if obj==self.collisionFiber:
                    continue
                if not self.legalParkTest(obj,lo,hi):
                    self.legal = False
                    break
                #if type(obj) in [Button,QGraphicsPolygonItem]:
                #    self.legal = False
        if not self.legal:
            self.plotFiber.setBrush(DarkRedBrush)

        if self.cable=='F':
            pen = self.plotFiber.pen()

        # MWAW -- this is just for engineering tests of fiber positioning
        self.plotButton.setToolTip("Fiber %s\nBend: %4.2f"%(self.fibid,self.psi))

    def legalParkTest(self,obj,lo,hi):
        objType = type(obj)
        testFibers = self.manager.Fibers
        if objType==Button:
            if lo in testFibers and testFibers[lo].plotButton==obj:
                return testFibers[lo].parked
            if hi in testFibers and testFibers[hi].plotButton==obj:
                return testFibers[hi].parked
            return False
        elif objType==QGraphicsPolygonItem:
            if lo in testFibers and testFibers[lo].collisionFiber==obj:
                return testFibers[lo].parked
            if hi in testFibers and testFibers[hi].collisionFiber==obj:
                return testFibers[hi].parked
            return False
        return True


    def drawFiber(self):
        # Allow dragging of the fiber is it is active
        self.plotButton.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable,self.active)
        pen = BlackButtonPen if self.active else GrayButtonPen
        self.plotButton.setPos(self.x,self.y)
        self.setFiber()
        if self.status!='A':
            self.plotButton.setBrush(GrayBrush)
        elif self.cable=='R':
            self.plotButton.setBrush(RedBrush)
        elif self.cable=='B':
            self.plotButton.setBrush(BlueBrush)
        elif self.cable=='F':
            self.plotButton.setBrush(YellowBrush)
        else:
            self.plotButton.setBrush(GrayBrush)
        self.plotButton.setPen(pen)

    def setActiveStatus(self,status):
        self.active = status
        self.drawFiber()

    def setQueueStatus(self,status):
        self.queued = status
        self.drawFiber()

    def updateXY(self,x,y):
        self.x,self.y = x,y
        self.drawFiber()

class StarMarker(QGraphicsPolygonItem):
    """
    Star marker for FOPS targets.
    """
    def __init__(self,size,objid):
        from math import cos,sin,tan,pi
        points = []
        # Ensure the size is the _bounding_ size and the star is centered
        scale = 1./4.9798  # Empirically
        offset = 0.0502    #  determined

        # Right point of upper triangle
        x0 = cos(54*pi/180)*scale
        y0 = sin(54*pi/180)*scale
        # Center point
        x1 = 0.
        y1 = y0+abs(x0)*tan(72*pi/180)
        # Left point
        x2 = -x0
        y2 = y0
        points = [[x0,y0],[x1,y1],[x2,y2]]
        # Rotate upper and left points by 1/5 of a circle and add to point list
        for i in range(4):
            angle = (i+1)*2*pi/5
            S,C = sin(angle),cos(angle)
            _x1 = x1*C-y1*S
            _y1 = x1*S+y1*C
            _x2 = x2*C-y2*S
            _y2 = x2*S+y2*C
            points += [[_x1,_y1],[_x2,_y2]]
        super(QGraphicsPolygonItem,self).__init__(QPolygonF([QPointF(_x*size,(offset-_y)*size) for _x,_y in points]))
        self.setBrush(YellowBrush)
        self.setPen(Pen)
        self.objid = objid

    def setAssigned(self,placed):
        if placed:
            self.setPen(PlacedPen)
        else:
            self.setPen(AssignedPen)

class SquareMarker(QGraphicsRectItem):
    """
    Square marker for science targets.
    """
    def __init__(self,size,objid):
        super(QGraphicsRectItem,self).__init__(-size/2,-size/2,size,size)
        self.setBrush(ScienceBrush)
        self.setPen(Pen)
        self.objid = objid
    def setAssigned(self,placed):
        if placed:
            self.setPen(PlacedPen)
        else:
            self.setPen(AssignedPen)

class CircleMarker(QGraphicsEllipseItem):
    """
    Circle marker for sky targets.
    """
    def __init__(self,size,objid):
        super(QGraphicsEllipseItem,self).__init__(-size/2,-size/2,size,size)
        self.setBrush(SkyBrush)
        self.setPen(Pen)
        self.objid = objid
    def setAssigned(self,placed):
        if placed:
            self.setPen(PlacedPen)
        else:
            self.setPen(AssignedPen)

