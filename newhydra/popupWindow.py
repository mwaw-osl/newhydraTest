from PyQt6 import *


class PopupWindow(QtWidgets.QWidget):
    def __init__(self, parent=None,addButtonBox=True):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)

        self.closed = False
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            PopupWindow {
                background: rgba(64, 64, 64, 64);
            }
            QWidget#container {
                border: 2px solid darkGray;
                border-radius: 4px;
                background: rgb(64, 64, 64);
            }
            QWidget#container > QLabel {
                color: white;
            }
            QLabel#title {
                font-size: 20pt;
            }
            QPushButton#close {
                color: white;
                font-weight: bold;
                background: none;
                border: 1px solid gray;
            }
        """)

        self.fullLayout = QtWidgets.QVBoxLayout(self)

        self.container = QtWidgets.QWidget(autoFillBackground=True, \
                objectName="container")
        self.fullLayout.addWidget(self.container, \
                alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.container.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, \
                QtWidgets.QSizePolicy.Policy.Maximum)

        buttonSize = self.fontMetrics().height()
        self.closeButton = QtWidgets.QPushButton('×', self.container, \
                objectName="close")
        self.closeButton.setFixedSize(buttonSize, buttonSize)
        self.closeButton.clicked.connect(self.close)

        self.layout = QtWidgets.QVBoxLayout(self.container)
        self.layout.setContentsMargins(buttonSize*2,buttonSize,buttonSize*2, \
                buttonSize)

        self.title = QtWidgets.QLabel('',
            objectName="title", alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        if addButtonBox:
            self.buttonBox = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok|QtWidgets.QDialogButtonBox.StandardButton.Cancel)
            self.layout.addWidget(self.buttonBox)
            self.buttonBox.accepted.connect(self.accept)
            self.buttonBox.rejected.connect(self.cancel)
            self.okButton = self.buttonBox.button(self.buttonBox.StandardButton.Ok)
            self.okButton.setEnabled(True)

        parent.installEventFilter(self)

        self.loop = QtCore.QEventLoop(self)

    def setTitle(self,title):
        self.title.setText(title)

    def cancel(self):
        self.loop.exit(False)

    def close(self):
        self.closed = True
        self.loop.quit()

    def showEvent(self, event):
        self.setGeometry(self.parent().rect())

    def resizeEvent(self, event):
        r = self.closeButton.rect()
        r.moveTopRight(self.container.rect().topRight() + QtCore.QPoint(-5, 5))
        self.closeButton.setGeometry(r)

    def accept(self):
        self.loop.exit(True)

    def exec_(self):
        self.show()
        self.raise_()
        res = self.loop.exec()
        self.hide()
        if self.closed:
            return None
        return res

class AssignFiberPopup(PopupWindow):
    def __init__(self,parent,obj=None,fib=None):
        super().__init__(parent)

        if fib is None and obj is None:
            self.setTitle("Assign an Object to a Fiber")
        elif fib is None:
            self.setTitle("Assign Object %s to a Fiber"%(obj))
        else:
            self.setTitle("Assign an Object to Fiber %s"%(fib))

        datacontainer = QtWidgets.QWidget(autoFillBackground=True, \
                objectName="container")
        self.layout.insertWidget(1,datacontainer, \
                alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        datacontainer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Maximum, \
                QtWidgets.QSizePolicy.Policy.Maximum)

        datalayout = QtWidgets.QGridLayout(datacontainer)
        datalayout.setContentsMargins(8,8,8,8)
        datalayout.setSpacing(4)
        datalayout.addWidget(QtWidgets.QLabel("Object:"),0,0,1,1)
        if obj is None:
            self.object = QtWidgets.QLineEdit()
        else:
            self.object = QtWidgets.QLabel(obj)
        datalayout.addWidget(self.object,0,1,1,1)
        datalayout.addWidget(QtWidgets.QLabel("Fiber:"),1,0,1,1)
        if fib is None:
            self.fiber = QtWidgets.QLineEdit()
        else:
            self.fiber = QtWidgets.QLabel(fib)
        datalayout.addWidget(self.fiber,1,1,1,1)

        if fib is None:
            self.fiber.returnPressed.connect(self.accept)
            self.fiber.setFocus()
        if obj is None:
            self.object.setFocus() # Take focus if both fib and obj are None
            self.object.returnPressed.connect(self.accept)

    def getData(self):
        if self.object.text().strip()!='' and self.fiber.text()!='':
            try:
                return [self.object.text().strip(),self.fiber.text().strip()]
            except:
                return False

    def accept(self):
        if self.getData():
            self.loop.exit(True)


class YesNoPopup(PopupWindow):
    def __init__(self,parent,title):
        super().__init__(parent)

        self.setTitle(title)

        for button in self.buttonBox.buttons():
            self.buttonBox.removeButton(button)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.StandardButton.No)
        self.buttonBox.addButton(QtWidgets.QDialogButtonBox.StandardButton.Yes)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.layout().setDirection(QtWidgets.QBoxLayout.Direction.RightToLeft)

    def accept(self):
        self.loop.exit(True)


class HowManyFibersPopup(PopupWindow):
    def __init__(self,parent,nfibers):
        super().__init__(parent)

        self.setTitle("How many low-weighted fibers\nshould be de-assigned?")
        self.spinBox = QtWidgets.QSpinBox()
        self.spinBox.setRange(1,nfibers)
        self.spinBox.setFixedWidth(50)
        self.layout.insertWidget(1,self.spinBox,alignment=QtCore.Qt.AlignmentFlag.AlignCenter)


    def getData(self):
        return self.spinBox.value()


