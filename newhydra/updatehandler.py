from PyQt6.QtWidgets import QTableWidgetItem,QLabel,QMenu
from PyQt6.QtGui import QColor,QPixmap
from PyQt6.QtCore import Qt,pyqtSlot,pyqtSignal
from PyQt6 import QtCore
ItemFlag = Qt.ItemFlag
import time




class UpdateHandler:

    @pyqtSlot(dict)
    def updateFiberStatus(self,fiberDB):
        self.DisplayManager.updateFiberDB(fiberDB)

    @pyqtSlot(dict)
    def updateFieldInfo(self,fieldData):
        """
        Update target/field information; this mostly resets the target table,
          but also calls the display manager to update the fiber display.
        """
        if fieldData is None:
            return
        fieldname = fieldData["name"]
        raStr = fieldData["raStr"]
        decStr = fieldData["decStr"]
        targets = fieldData["targets"]
        angle = fieldData["angle"]

        # Set the mapping from plate to sky
        #self.FieldModel.setInfo(fieldData["RA"],fieldData["DEC"],angle)

        T = "%s\nRA:  %s\nDEC: %s"%(fieldname,raStr[:11],decStr[:11])
        self.fieldname_label.setText(T)
        self.fieldinfo.show()
        self.showmarkers.show()
        self.updateFiberTable(targets,angle)

    def updateFiberTable(self,targets,angle=None):
        count = 0
        fibCount = {'F':0,'S':0,'O':0,'C':0}

        # We temporarily disable visibility because rendering the table whilst
        #   building it can be very slow
        self.FiberTable.setVisible(False)
        self.FiberTable.clearContents()
        self.FiberTable.setSortingEnabled(False)
        self.FiberTable.setRowCount(len(targets))
        for count,(objid,data) in enumerate(targets.items()):
            objid = "{:4d}".format(int(objid))
            # Color-code the rows according to target type
            if data["type"]=='F':
                C = QColor("lightYellow")
            elif data["type"]=='S':
                C = QColor(200,200,255)
            else:
                C = QColor(200,255,200)
            tmpItem = QTableWidgetItem(objid)
            tmpItem.setBackground(C)
            tmpItem.setFlags(tmpItem.flags()^ItemFlag.ItemIsEditable)
            self.FiberTable.setItem(count,0,tmpItem)
            for col,val in enumerate(("name","mag","ra","dec")):
                col += 1
                tmpItem = QTableWidgetItem(data[val])
                tmpItem.setBackground(C)
                tmpItem.setFlags(tmpItem.flags()^ItemFlag.ItemIsEditable)
                self.FiberTable.setItem(count,col,tmpItem)
            fibid = ""
            slitid = ""
            # Add fibid/slitid if the target is assigned to a fiber, and
            #  change the color to pink if the fiber is placed.
            if data["fibid"] is not None:
                fibid = "{:3d}".format(data["fibid"])
                fibCount[data["type"]] += 1
                if data["slitid"]>0:
                    slitid = "{:3d}".format(data["slitid"])
                C = QColor("pink")

            # We use a blank QLabel for the fiber/slit in any rows that
            #  DO NOT have a fiber assigned so that they will always be
            #  sorted to the bottom when sorting by fiber/slit.
            colorName = C.name()
            if fibid=="":
                tmpItem = QLabel()
                tmpItem.setStyleSheet("QLabel { background-color: %s }"%(colorName))
                self.FiberTable.setCellWidget(count,5,tmpItem)
            else:
                tmpItem = QTableWidgetItem(fibid)
                tmpItem.setBackground(C)
                tmpItem.setFlags(tmpItem.flags()^ItemFlag.ItemIsEditable)
                self.FiberTable.setItem(count,5,tmpItem)
            if slitid=="":
                tmpItem = QLabel()
                tmpItem.setStyleSheet("QLabel { background-color: %s }"%(colorName))
                self.FiberTable.setCellWidget(count,6,tmpItem)
            else:
                tmpItem = QTableWidgetItem(slitid)
                tmpItem.setBackground(C)
                tmpItem.setFlags(tmpItem.flags()^ItemFlag.ItemIsEditable)
                self.FiberTable.setItem(count,6,tmpItem)
        # Re-enable viewing
        self.FiberTable.setSortingEnabled(True)
        self.FiberTable.setVisible(True)
        # Update the fiber count table
        countStr = "{:3d}".format(fibCount['O'])
        self.fiberCountTable.setItem(1,1,QTableWidgetItem(countStr))
        countStr = "{:3d}".format(fibCount['S'])
        self.fiberCountTable.setItem(2,1,QTableWidgetItem(countStr))
        countStr = "{:3d}".format(fibCount['F'])
        self.fiberCountTable.setItem(3,1,QTableWidgetItem(countStr))
        self.fiberCountTable.setVisible(True)
        # Update the fiber display, including the compasses
        self.DisplayManager.updateTargetDB(targets,angle)

    def fiberTableAction(self,pos):
        """
        """
        row = self.FiberTable.rowAt(pos.y())
        col = self.FiberTable.columnAt(pos.x())
        if self.FiberTable.item(row,0) is None:
            return
        obj = self.FiberTable.item(row,0).text()
        name = self.FiberTable.item(row,1).text()
        fib = self.FiberTable.item(row,5)

        assigned = fib is not None
        menu = QMenu()
        _ = menu.addSection(name.strip())
        blink = menu.addAction("Show marker")
        blink.triggered.connect(lambda: self.DisplayManager.startMarkerBlink(int(obj)))
        if assigned:
            fib = fib.text()
            deassign = menu.addAction("Deassign Fiber")
            deassign.triggered.connect(lambda: self.assignFiber(obj=obj,fib=fib,remove=True))
        menu.exec(self.FiberTable.viewport().mapToGlobal(pos))
