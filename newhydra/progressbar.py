from PyQt6 import *


class ProgressWindow(QtWidgets.QWidget):
    def __init__(self, parent=None,addScoreLabel=False):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)

        self.closed = False
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            ProgressWindow {
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

        self.layout = QtWidgets.QVBoxLayout(self.container)
        self.layout.setContentsMargins(buttonSize*2,buttonSize,buttonSize*2, \
                buttonSize)

        self.title = QtWidgets.QLabel('',
            objectName="title", alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.title)

        self.progressBar = QtWidgets.QProgressBar(self)
        self.layout.addWidget(self.progressBar)

        if addScoreLabel:
            self.scoreLabel = QtWidgets.QLabel('score = 0',objectName="scorelable", alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.scoreLabel)


        parent.installEventFilter(self)
        self.loop = QtCore.QEventLoop(self)

    def setTitle(self,title):
        self.title.setText(title)

    def showEvent(self, event):
        self.setGeometry(self.parent().rect())

#    def resizeEvent(self, event):
#        r = self.closeButton.rect()
#        r.moveTopRight(self.container.rect().topRight() + QtCore.QPoint(-5, 5))
#        self.closeButton.setGeometry(r)

    @QtCore.pyqtSlot(int)
    def updateProgress(self,percent):
        self.progressBar.setValue(percent)
        if percent==100:
            self.loop.quit()

    @QtCore.pyqtSlot(int)
    def updateScoreLabel(self,score):
        self.scoreLabel.setText("score = {}".format(score))

    def exec_(self):
        self.show()
        self.raise_()
        res = self.loop.exec()
        self.hide()
        if self.closed:
            return None
        return res

