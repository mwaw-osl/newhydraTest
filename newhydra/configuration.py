
class ConfigLists:
    def __init__(self):
        self.IDs = []
        self.weights = []
        self.flags = []
        self.score = 0
        self.nitems = 0

    def addItem(self,newID,newWeight,newFlag):
        self.IDs.append(newID)
        self.weights.append(newWeight)
        self.flags.append(newFlag)
        self.score += newWeight
        self.nitems += 1

    def getID(self,index):
        if index>=0 and index<self.nitems:
            return self.IDs[index]

    def getFlag(self,index):
        if index>=0 and index<self.nitems:
            return self.flags[index]

    def getWeight(self,index):
        if index>=0 and index<self.nitems:
            return self.weights[index]

    def getIndex(self,ID):
        if ID in self.IDs:
            return self.IDs.index(ID)

    def update(self,index,newID,newWeight,newFlag):
        self.IDs[index] = newID
        self.weights[index] = newWeight
        self.flags[index] = newFlag
        self.score = sum(self.weights)

class Configuration:
    currentConfig = ConfigLists()

    def zeroCurrentConfig(self):
        self.currentConfig = ConfigLists()
        self.reset_btn.setEnabled(False)
        self.reset_btn.setText("No\nConfiguration")

    def resetCurrentConfig(self,removeManual=False):
        for index,flag in enumerate(self.currentConfig.flags):
            if removeManual or not flag:
                    self.currentConfig.update(index,None,0,False)
        self.reset_btn.setEnabled(False)
        self.reset_btn.setText("No\nConfiguration")

    def addToCurrentConfig(self,ID,weight,flag):
        self.currentConfig.addItem(ID,weight,flag)

    def getCurrentConfigID(self,index):
        return self.currentConfig.getID(index)

    def getCurrentConfigFlag(self,index):
        return self.currentConfig.getFlag(index)

    def getCurrentConfigWeight(self,index):
        return self.currentConfig.getWeight(index)

    def getCurrentConfigIndex(self,ID):
        return self.currentConfig.getIndex(ID)

    def updateCurrentConfig(self,index,newID,newWeight,newFlag):
        self.currentConfig.update(index,newID,newWeight,newFlag)

    def copyCurrentConfig(self):
        tmp = ConfigLists()
        tmp.IDs = [_ for _ in self.currentConfig.IDs]
        tmp.weights = [_ for _ in self.currentConfig.weights]
        tmp.flags = [_ for _ in self.currentConfig.flags]
        tmp.score = self.currentConfig.score
        return tmp

    def restoreCurrentConfig(self,config):
        self.currentConfig.IDs = [_ for _ in config.IDs]
        self.currentConfig.weights = [_ for _ in config.weights]
        self.currentConfig.flags = [_ for _ in config.flags]
        self.currentConfig.score = config.score

    def iterateCurrentConfig(self):
        for X in enumerate(self.currentConfig.IDs):
            yield X

    def iterateCurrentFlags(self):
        for X in enumerate(self.currentConfig.flags):
            yield X

    def updateBestConfig(self):
        if self.currentConfig.score>0:
            self.reset_btn.setEnabled(True)
            self.reset_btn.setText("Reset Score:\n%d"%(int(self.currentConfig.score)))
