from PyQt6.QtCore import QRunnable,QObject,pyqtSignal,pyqtSlot
import traceback,sys
class QtSignals(QObject): 
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    finished = pyqtSignal()

class Worker(QRunnable):

    def __init__(self,func,*args):
        super(Worker,self).__init__()

        self.func = func
        self.args = args
        self.signals = QtSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.func(*self.args)
        except:
            traceback.print_exc()
            exctype,value = sys.exc_info()[:2]
            self.signals.error.emit((exctype,value,traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

