import sys
import os
import cv2
import json
import numpy as np
from PIL import Image, ExifTags
from glob import glob
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QFileDialog, QLabel
from PyQt5.QtWidgets import QDesktopWidget, QMessageBox
from PyQt5.QtGui import QPixmap, QPainter, QPen, QFont, QColor
from PyQt5.QtCore import QPoint
from sample_view import GroupModel, GroupView
import csv


class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.mainWidget = MainWidget(self)

        self.setCentralWidget(self.mainWidget)
        statusbar = self.statusBar()
        self.setStatusBar(statusbar)
        self.fileName = QLabel('Ready')
        self.cursorPos = QLabel('      ')
        self.imageSize = QLabel('      ')
        self.autoLabel = QLabel('Manual Label')
        self.progress = QLabel('                 ')  # reserve widget space

        widget = QWidget(self)
        widget.setLayout(QHBoxLayout())
        widget.layout().addWidget(self.fileName)
        widget.layout().addStretch(1)
        widget.layout().addWidget(self.imageSize)
        widget.layout().addWidget(self.cursorPos)
        widget.layout().addStretch(1)
        widget.layout().addWidget(self.autoLabel)
        widget.layout().addStretch(2)
        widget.layout().addWidget(self.progress)
        statusbar.addWidget(widget, 1)

        self.setGeometry(50, 50, 1200, 800)
        self.setWindowTitle('pyYoloMark')
        self.show()

    def fitSize(self):
        self.setFixedSize(self.layout().sizeHint())


class SampleGrouper(object):

    """Group samples Object for image"""

    def __init__(self, categories):
        self.categories = categories
        self.categories_color = {}
        self.samples = []
        self.new_samples = []
        self.line_number = None

    def addSample(self, sample):
        if sample.idx is None:
            raise Exception(
                "Sample must be idx before appending to Gruper"
            )
        self.samples.append(sample)
        if sample.isNew():
            self.new_samples.append(sample)
        if sample.idx not in self.categories_color:
            self.categories_color[sample.idx] = list(
                np.random.choice(range(256), size=3)
            ) + [255]

    def getCategories(self):
        return {
            i: name
            for i, name in self.categories.items()
        }

    def getSamplesToRender(self):
        return filter(lambda x: x.isVisible(), self.samples)

    def getSamplesToRenderGrouped(self):
        groups = {}
        for sample in self.samples:
            if not sample.isVisible():
                continue
            if sample.idx not in groups:
                groups[sample.idx] = []
            groups[sample.idx].append(sample)
        return groups

    def getSamplesGrouped(self):
        groups = {}
        for sample in self.samples:
            if sample.idx not in groups:
                groups[sample.idx] = []
            groups[sample.idx].append(sample)
        return groups

    def needToSave(self):
        return bool(self.new_samples)

    def setGroupVisibility(self, idx, visible):
        for sample in self.samples:
            if sample.idx != idx:
                continue
            if visible:
                sample.setVisible()
            else:
                sample.setInvisible()
        return True

class SampleObject(object):

    def __init__(self, ratio=(1, 1)):
        if len(ratio) != 2:
            raise Exception("Bad Ratio. Must be (float, float)")
        self.idx = None
        self._W = ratio[0]
        self._H = ratio[1]
        self._visible = True
        self._new_idx = None
        self._new = False
        self._changed = False

    def isNew(self):
        return self._new

    def isVisible(self):
        return self._visible

    def withChanges(self):
        return self._changed

    def setInvisible(self):
        self._visible = False
        return True

    def setVisible(self):
        self._visible = True
        return True

    def setCategory(self, idx):
        self._new_idx = idx
        self._changed = True
        return True

    def resetCategory(self):
        if self._new_idx:
            self._new_idx = None
            self._changed = False
        return True

    def addYoloCfg(self, line_number, pos_cfg, categories={}):
        self.idx = int(pos_cfg[0])
        if not categories.get(self.idx, False):
            raise Exception("Category not found for index %s" % self.idx)
        self.line_number = line_number
        self.category_name = categories[self.idx]
        self.center_x = float(pos_cfg[1])
        self.center_y = float(pos_cfg[2])
        self.width = float(pos_cfg[3])
        self.height = float(pos_cfg[4])
        self.lx = (self.center_x - (self.width / 2)) * self._W
        self.rx = (self.center_x + (self.width / 2)) * self._W
        self.ly = (self.center_y - (self.height / 2)) * self._H
        self.ry = (self.center_y + (self.height / 2)) * self._H
        return True

    def getBoxFormat(self):
        if self.idx is None:
            raise Exception("SampleObject not initialized with cfg")
        # box : (lx, ly, rx, ry, idx)
        box = (
            self.lx, self.ly,
            self.rx, self.ry,
            self.idx,
        )
        return box

    def getYoloFormat(self):
        if self.idx is None:
            raise Exception("SampleObject not initialized with cfg")
        # yolo (obj_cfg) : (idx center_x_ratio, center_y_ratio,
        #         width_ratio, height_ratio)
        yolo_format = [
            self.idx,
            (self.lx + self.rx)/2/self._W,
            (self.ly + self.ry)/2/self._H,
            (self.rx - self.lx)/self._W,
            (self.ry - self.ly)/self._H
        ]
        return yolo_format

    def addBox(self, lx, ly, rx, ry, idx, category_name):
        self._new = True
        self.idx = idx
        self.category_name = category_name
        self.lx = lx
        self.ly = ly
        self.rx = rx
        self.ry = ry
        self.idx = idx
        return True


class ImageWidget(QWidget):
    def __init__(self, parent):
        super(ImageWidget, self).__init__(parent)
        self.parent = parent
        self.results = []
        self.setMouseTracking(True)
        self.screen_height = QDesktopWidget().screenGeometry().height()
        self.last_idx = 0

        self.initUI()

    def initUI(self):
        self.pixmap = QPixmap('./resources/background/start.png')
        self.label_img = QLabel()
        self.label_img.setObjectName("image")
        self.pixmapOriginal = QPixmap.copy(self.pixmap)

        self.drawing = False
        self.lastPoint = QPoint()
        hbox = QHBoxLayout(self.label_img)
        self.setLayout(hbox)
        # self.setFixedSize(1200,800)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)

    def showPopupOk(self, title: str, content: str):
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(content)
        msg.setStandardButtons(QMessageBox.Ok)
        result = msg.exec_()
        if result == QMessageBox.Ok:
            msg.close()

    def drawSamplesBox(self):
        res = QPixmap.copy(self.pixmapOriginal)
        painter = QPainter(res)
        font = QFont('mono', 10, 1)
        painter.setFont(font)
        # Dibujamos por grupos
        groups = self.grouper.getSamplesToRenderGrouped()
        for gindex, samples in groups.items():
            gcolor = self.grouper.categories_color[gindex]
            qcolor = QColor(*gcolor)
            for sample in samples:
                painter.setPen(QPen(qcolor, 2, Qt.SolidLine))
                painter.drawRect(sample.lx, sample.ly,
                                 sample.rx - sample.lx,
                                 sample.ry - sample.ly)
                # Draw text
                painter.setPen(QPen(Qt.blue, 2, Qt.SolidLine))
                painter.drawText(sample.lx, sample.ly+15,
                                 sample.category_name)
        return res

    def setPixmap(self, image_fn):
        self.pixmap = QPixmap(image_fn)
        self.W, self.H = self.pixmap.width(), self.pixmap.height()

        if self.H > self.screen_height * 0.8:
            resize_ratio = (self.screen_height * 0.8) / self.H
            self.W = round(self.W * resize_ratio)
            self.H = round(self.H * resize_ratio)
            self.pixmap = QPixmap.scaled(self.pixmap, self.W, self.H,
                                         transformMode=Qt.SmoothTransformation)

        self.parent.imageSize.setText('{}x{}'.format(self.W, self.H))
        self.setFixedSize(self.W, self.H)
        self.pixmapOriginal = QPixmap.copy(self.pixmap)

    def _getObjCfg(self, obj_data):
        # box : (lx, ly, rx, ry, idx)
        # yolo (obj_cfg) : (idx center_x_ratio, center_y_ratio,
        #         width_ratio, height_ratio)
        W, H = self.getRatio()
        center_x = float(obj_data[1])
        center_y = float(obj_data[2])
        width = float(obj_data[3])
        height = float(obj_data[4])
        vals = {
            'idx': int(obj_data[0]),
            'center_x': center_x,
            'center_y': center_y,
            'width': width,
            'height': height,
            'lx': (center_x - (width / 2)) * W,
            'rx': (center_x + (width / 2)) * W,
            'ly': (center_y - (height / 2)) * H,
            'ry': (center_y + (height / 2)) * H,
        }
        return vals

    def setObjData(self, obj_datas):
        """
        Read image txt and draw created boxes
        """
        # Create new grouper
        categories = self.parent.mainWidget.categories
        self.grouper = SampleGrouper(categories)
        self.resetResult()
        for line_number, obj_data in enumerate(obj_datas):
            sample = SampleObject(ratio=self.getRatio())
            sample.addYoloCfg(line_number, obj_data, categories=categories)
            self.grouper.addSample(sample)
            box = sample.getBoxFormat()
            self.results.append(box)
        self.parent.mainWidget.refreshTreeView()
        self.pixmap = self.drawSamplesBox()
        self.update()

    def cancelLast(self):
        if self.results:
            self.results.pop()  # pop last
            self.pixmap = self.drawResultBox()
            self.update()

    def getRatio(self):
        return self.W, self.H

    def getResult(self):
        return self.results

    def resetResult(self):
        self.results = []

    def markBox(self, idx):
        self.last_idx = idx
        if self.results:
            if len(self.results[-1]) == 4:
                self.results[-1].append(idx)
            elif len(self.results[-1]) == 5:
                self.results[-1][-1] = idx
            else:
                raise ValueError('invalid results')
            self.pixmap = self.drawResultBox()
            self.update()


class MainWidget(QWidget):
    def __init__(self, parent):
        super(MainWidget, self).__init__(parent)
        self.parent = parent
        self.currentImg = "start.png"
        config_dict = self.getConfigFromJson('config.json')
        self.image_directory = None
        self.train_path = None
        self.obj_names_path = None
        self.categories = {}
        self.initUI()

    def showPopupOk(self, title, content):
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(content)
        msg.setStandardButtons(QMessageBox.Ok)
        result = msg.exec_()
        if result == QMessageBox.Ok:
            msg.close()

    def refreshTreeView(self):
        render = self.label_img
        samples_grouped = render.grouper.getSamplesGrouped()
        for idx, samples in samples_grouped.items():
            group_name = render.grouper.categories[idx]
            group_item = self.group_model.add_group(idx, group_name)
            for sample in samples:
                self.group_model.append_element_to_group(group_item, sample)
        try:
            self.group_model.disconnect(self.registerTreeCellChange)
        except Exception:
            pass
        self.group_model.itemChanged.connect(self.registerTreeCellChange)
        return True

    def registerTreeCellChange(self, item):
        if getattr(self, '_on_register_tree_cell', False):
            return True
        item_data = item.data()
        self._on_register_tree_cell = True
        if isinstance(item_data, int):  # Grouper
            self.label_img.grouper.setGroupVisibility(
                item_data, bool(item.checkState())
            )
            # Root element:
            root = item.data(3)
            for row in range(0, root.rowCount()):
                root.child(row, 1).setCheckState(item.checkState())
            self.label_img.pixmap = self.label_img.drawSamplesBox()
            self.label_img.update()
        elif isinstance(item_data, SampleObject):
            # Cambio la categoria?
            if item.column() == 2:
                item.setForeground(QColor("#000000"))
                if not item.data(2):
                    self._on_register_tree_cell = False
                    item_data.resetCategory()
                    return
                try:
                    category_index = int(item.data(2).strip())
                except Exception:
                    self.showPopupOk(
                        "Error!", "Category must be integer"
                    )
                    item.setData("", 2)
                    self._on_register_tree_cell = False
                    return
                if category_index not in self.categories:
                    self.showPopupOk(
                        "Error!",
                        "Category index must be in %s. \n Categories: %s"
                        % (
                            str(list(self.categories.keys())),
                            str(self.categories),
                        )
                    )
                    item.setData("", 2)
                    self._on_register_tree_cell = False
                    return
                item_data.setCategory(category_index)
                item.setForeground(QColor("#FF0000"))
            else:
                if bool(item.checkState()):
                    item_data.setVisible()
                else:
                    item_data.setInvisible()
                self.label_img.pixmap = self.label_img.drawSamplesBox()
                self.label_img.update()
        self._on_register_tree_cell = False
        return True

    def initUI(self):
        # UI elements
        imagePathButton = QPushButton('Image Path (Folder)', self)
        objNamesPathButton = QPushButton('obj.names File Path', self)

        self.okButton = QPushButton('Next', self)
        cancelButton = QPushButton('Cancel', self)
        imagePathLabel = QLabel('Image Path not selected', self)
        objNamesPathLabel = QLabel('obj.names Path not selected', self)

        self.label_img = ImageWidget(self.parent)

        # Events
        self.okButton.clicked.connect(self.setNextImage)
        self.okButton.setEnabled(False)
        cancelButton.clicked.connect(self.label_img.cancelLast)
        imagePathButton.clicked.connect(
            lambda: self.registerImagePath(
                imagePathButton, imagePathLabel)
        )
        objNamesPathButton.clicked.connect(
            lambda: self.registerObjNamesPath(
                objNamesPathButton, objNamesPathLabel)
        )

        # Config Button
        hbox = QHBoxLayout()

        vbox = QVBoxLayout()
        vbox.addWidget(imagePathButton)
        vbox.addWidget(objNamesPathButton)
        hbox.addLayout(vbox)

        vbox = QVBoxLayout()
        vbox.addWidget(imagePathLabel)
        vbox.addWidget(objNamesPathLabel)
        hbox.addLayout(vbox)

        hbox.addStretch(3)
        hbox.addStretch(1)
        hbox.addWidget(self.okButton)
        hbox.addWidget(cancelButton)

        vbox = QVBoxLayout()
        hbox_1 = QHBoxLayout()
        hbox_1.addWidget(self.label_img, 7)
        self.group_model = GroupModel(self)
        self.tree_view = GroupView(self.group_model)
        hbox_1.addWidget(self.tree_view, 3)
        vbox.addLayout(hbox_1)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

    def setNextImage(self):
        res = self.label_img.getResult()
        self.group_model.removeRows(0, self.group_model.rowCount())
        self.writeResults(res)
        self.label_img.resetResult()
        try:
            self.currentImg = self.imgList.pop(0)
            self.currentCfg = self.imgListCfg.pop(0)
        except Exception:
            self.currentImg = './resources/background/end.png'
            self.currentCfg = ''
            self.okButton.setEnabled(False)

        basename = os.path.basename(self.currentImg)
        self.parent.fileName.setText(basename)
        self.parent.progress.setText(
            str(self.total_imgs-len(self.imgList)) +
            '/'+str(self.total_imgs)
        )

        self.label_img.setPixmap(self.currentImg)
        self.label_img.update()
        self.parent.fitSize()
        with open(self.currentCfg, 'r') as f:
            cfg = csv.reader(f, delimiter=' ', dialect='skip_space')
            self.label_img.setObjData(cfg)

    def enableOkButton(self):
        if self.image_directory and self.obj_names_path:
            self.okButton.setEnabled(True)
        else:
            self.okButton.setEnabled(False)
        return True

    def writeResults(self, res):
        if self.parent.fileName.text() != 'Ready':
            W, H = self.label_img.getRatio()
            if not res:
                open(self.currentImg[:-4]+'.txt', 'a', encoding='utf8').close()
            for i, elements in enumerate(res):  # box : (lx, ly, rx, ry, idx)
                lx, ly, rx, ry, idx = elements
                # yolo : (idx center_x_ratio, center_y_ratio,
                #         width_ratio, height_ratio)
                yolo_format = [idx, (lx+rx)/2/W, (ly+ry)/2/H,
                               (rx-lx)/W, (ry-ly)/H]
                with open(self.currentImg[:-4]+'.txt', 'a', encoding='utf8') as resultFile:
                    resultFile.write(' '.join([str(x) for x in yolo_format]) + '\n')

    def registerImagePath(self, imagePathButton, imagePathLabel):
        imagePathButton.toggle()
        directory = str(
            QFileDialog.getExistingDirectory(self, "Select Input Directory")
        )
        basename = os.path.basename(directory)
        if not basename:
            print("Input Path not selected")
            return -1
        self.image_directory = basename

        types = ('*.jpg', '*.png', '*.jpeg')
        self.imgList = []
        for t in types:
            self.imgList.extend(glob(directory+'/'+t))
        self.total_imgs = len(self.imgList)

        self.imgListCfg = []
        for imgPath in self.imgList:
            fsize = 4
            if '.' not in imgPath[:-5]:
                fsize = 5
            if os.path.exists(imgPath[:-fsize] + '.txt'):
                self.imgListCfg.append(imgPath[:-fsize] + '.txt')
            else:
                print("Txt not found: %s" % (imgPath[:-fsize] + '.txt'))
                self.imgList.remove(imgPath)
        imagePathLabel.setText(basename+'/')
        self.enableOkButton()

    def registerObjNamesPath(self, objNamesPathButton, objNamesPathLabel):
        """
        Read object.names and save categories
        """
        objNamesPathButton.toggle()
        file_path = QFileDialog.getOpenFileName(
            self, "Select Train file", filter="*.names")[0]
        file_name = os.path.basename(file_path)
        if not file_name:
            print("Obj Names file Path not selected")
            return -1
        objNamesPathLabel.setText(file_name)
        self.obj_names_path = file_path

        # Read Objects names
        with open(file_path, 'r') as f:
            obj_names = f.readlines()
            self.categories = {
                i: name.replace('\n', '')
                for i, name in enumerate(obj_names)
            }
        self.enableOkButton()
        return

    def getConfigFromJson(self, json_file):
        # parse the configurations from the config json file provided
        with open(json_file, 'r') as config_file:
            try:
                config_dict = json.load(config_file)
                # EasyDict allows to access dict values
                # as attributes (works recursively).
                return config_dict
            except ValueError:
                print("INVALID JSON file format.. "
                      "Please provide a good json file")
                exit(-1)


if __name__ == '__main__':
    csv.register_dialect('skip_space', skipinitialspace=True)
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())
