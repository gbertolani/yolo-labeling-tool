import sys
import os
import numpy as np
from glob import glob
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QFileDialog, QLabel
from PyQt5.QtWidgets import QDesktopWidget, QMessageBox
from PyQt5.QtGui import QPixmap, QPainter, QPen, QFont, QColor
from PyQt5.QtCore import QPoint
from sample_view import GroupModel, GroupView
import csv
import math
import re


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
        self.progress = QLabel('                 ')  # reserve widget space

        widget = QWidget(self)
        widget.setLayout(QHBoxLayout())
        widget.layout().addWidget(self.fileName)
        widget.layout().addStretch(1)
        widget.layout().addWidget(self.imageSize)
        widget.layout().addWidget(self.cursorPos)
        widget.layout().addStretch(1)
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

    def getSamplesGrouped(self, only_visible=False):
        """
        Return samples grouped
        if only_visible is True only return visible samples
        """
        groups = {}
        for sample in self.samples:
            if not sample.isVisible() and only_visible:
                continue
            if sample.idx not in groups:
                groups[sample.idx] = []
            groups[sample.idx].append(sample)
        return groups

    def prepareSamplesToSave(self):
        """
        Return samples changed grouped
        by cateogry to save
        """
        groups = {}
        for sample in self.samples:
            sample_idx = sample.getFinalIdx()
            if sample_idx not in groups:
                groups[sample_idx] = []
            groups[sample_idx].append(sample)
        return groups

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

    def _truncate(self, number):
        """
        Returns a value truncated to a specific
        number of decimal places.
        """
        factor = 10.0 ** 6
        number += 0.0000001 # Sum lost decimals
        return str(math.trunc(number * factor) / factor).ljust(8, '0')

    def getFinalIdx(self):
        idx = self._new_idx
        if self._new_idx is None:
            idx = self.idx
        return idx

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

    def needToSave(self):
        return bool(self._changed)

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
            str(self.getFinalIdx()),
            self._truncate((self.lx + self.rx)/2/self._W),
            self._truncate((self.ly + self.ry)/2/self._H),
            self._truncate((self.rx - self.lx)/self._W),
            self._truncate((self.ry - self.ly)/self._H),
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
        groups = self.grouper.getSamplesGrouped(only_visible=True)
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

    def setObjData(self, obj_path):
        """
        Read image txt and draw created boxes
        """
        # Create new grouper
        main_widget = self.parent.mainWidget
        categories = main_widget.categories
        self.grouper = SampleGrouper(categories)
        self.resetResult()
        main_widget.group_model.removeRows(
            0, main_widget.group_model.rowCount()
        )
        if not obj_path:
            return False
        with open(obj_path, 'r') as f:
            obj_datas = csv.reader(f, delimiter=' ', dialect='skip_space')
            for line_number, obj_data in enumerate(obj_datas):
                if len(obj_data) != 5:
                    raise Exception(
                        "Invalid config file: %s \n. Line %s.\n"
                        "Expected 5 elements: %s"
                        % (main_widget.currentCfg, line_number, str(obj_data))
                    )
                sample = SampleObject(ratio=self.getRatio())
                sample.addYoloCfg(line_number, obj_data,
                                  categories=categories)
                self.grouper.addSample(sample)
                box = sample.getBoxFormat()
                self.results.append(box)
        main_widget.refreshTreeView()
        self.pixmap = self.drawSamplesBox()
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
            self.pixmap = self.drawSamplesBox()
            self.update()


class MainWidget(QWidget):

    def __init__(self, parent):
        super(MainWidget, self).__init__(parent)
        self.parent = parent
        self.currentImg = "start.png"
        self.currentCfg = ""
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

        self.backButton = QPushButton('Back', self)
        self.okButton = QPushButton('Next', self)
        imagePathLabel = QLabel('Image Path not selected', self)
        objNamesPathLabel = QLabel('obj.names Path not selected', self)

        self.label_img = ImageWidget(self.parent)
        self.image_index = -1

        # Events
        self.okButton.clicked.connect(
            lambda: self.setNextImage()
        )
        self.backButton.clicked.connect(
            lambda: self.setNextImage(go_back=True)
        )
        self.okButton.setEnabled(False)
        self.backButton.setEnabled(False)
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
        hbox.addWidget(self.backButton)
        hbox.addWidget(self.okButton)

        vbox = QVBoxLayout()
        hbox_1 = QHBoxLayout()
        hbox_1.addWidget(self.label_img, 7)
        self.group_model = GroupModel(self)
        self.tree_view = GroupView(self.group_model)
        hbox_1.addWidget(self.tree_view, 3)
        vbox.addLayout(hbox_1)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

    def setNextImage(self, go_back=False):
        if go_back:
            self.image_index -= 1
        else:
            self.image_index += 1
        self.writeSamples()
        # start?
        if self.image_index < 0:
            self.currentImg = './resources/background/start.png'
            self.currentCfg = ''
            self.backButton.setEnabled(False)
            self.parent.progress.setText("")
        else:
            try:
                self.currentImg = self.imgList[self.image_index]
                self.currentCfg = self.imgListCfg[self.image_index]
            except Exception:
                self.currentImg = './resources/background/end.png'
                self.currentCfg = ''
                self.okButton.setEnabled(False)
            self.backButton.setEnabled(True)
            self.parent.progress.setText(
                str(self.image_index) +
                '/'+str(self.total_imgs)
            )

        basename = os.path.basename(self.currentImg)
        self.parent.fileName.setText(basename)
        self.label_img.setPixmap(self.currentImg)
        self.label_img.update()
        self.parent.fitSize()
        self.label_img.setObjData(self.currentCfg)

    def enableOkButton(self):
        if self.image_directory and self.obj_names_path:
            self.okButton.setEnabled(True)
        else:
            self.okButton.setEnabled(False)
        return True

    def writeSamples(self):
        if not self.currentCfg:
            return True
        groups = self.label_img.grouper.prepareSamplesToSave()
        with open(self.currentCfg, 'r+', encoding='utf8') as file:
            file.truncate(0)
            groups_keys = list(groups.keys())
            groups_keys.sort()
            for group_idx in groups_keys:
                samples = groups[group_idx]
                for sample in samples:
                    writer = csv.writer(file, delimiter=' ', dialect='skip_space')
                    writer.writerow(sample.getYoloFormat())
        return True

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
        # Sort img List
        self.imgList.sort()
        self.total_imgs = len(self.imgList)

        self.imgListCfg = []
        for imgPath in self.imgList:
            if 'predicted' in imgPath:
                self.imgList.remove(imgPath)
                continue
            txt_path = imgPath
            for type in types:
                txt_path = re.sub('.' + type + '$', '.txt', txt_path)
            if txt_path == imgPath:
                print("Txt not found: %s" % (imgPath))
                self.imgList.remove(imgPath)
                continue
            if os.path.exists(txt_path):
                self.imgListCfg.append(txt_path)
            else:
                print("Txt not found: %s" % (txt_path))
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


if __name__ == '__main__':
    csv.register_dialect('skip_space', skipinitialspace=True)
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())
