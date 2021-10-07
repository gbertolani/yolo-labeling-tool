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
        self.categories = {}
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

    def needToSave(self):
        return bool(new_samples)

class SampleObject(object):

    def __init__(self, ratio=(1, 1)):
        if len(ratio) != 2:
            raise Exception("Bad Ratio. Must be (float, float)")
        self.idx = None
        self._W = ratio[0]
        self._H = ratio[1]
        self._visible = True
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

    def setCategory(self, idx, category_name):
        self.category_name = category_name
        self.idx = idx
        self._changed = True
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
    def __init__(self, parent, key_cfg):
        super(ImageWidget, self).__init__(parent)
        self.parent = parent
        self.results = []
        self.setMouseTracking(True)
        self.key_config = key_cfg
        self.screen_height = QDesktopWidget().screenGeometry().height()
        self.last_idx = 0

        self.initUI()

    def initUI(self):
        self.pixmap = QPixmap('start.png')
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

    # def mousePressEvent(self, event):
    #     if event.button() == Qt.LeftButton:
    #         self.prev_pixmap = self.pixmap
    #         self.drawing = True
    #         self.lastPoint = event.pos()
    #     elif event.button() == Qt.RightButton:
    #         x, y = event.pos().x(), event.pos().y()
    #         for i, box in enumerate(self.results):
    #             lx, ly, rx, ry = box[:4]
    #             if lx <= x <= rx and ly <= y <= ry:
    #                 self.results.pop(i)
    #                 self.pixmap = self.drawResultBox()
    #                 self.update()
    #                 break
    #
    # def mouseMoveEvent(self, event):
    #     self.parent.cursorPos.setText(
    #         '({}, {})'.format(event.pos().x(), event.pos().y()))
    #     if event.buttons() and Qt.LeftButton and self.drawing:
    #         self.pixmap = QPixmap.copy(self.prev_pixmap)
    #         painter = QPainter(self.pixmap)
    #         painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
    #         p1_x, p1_y = self.lastPoint.x(), self.lastPoint.y()
    #         p2_x, p2_y = event.pos().x(), event.pos().y()
    #         painter.drawRect(min(p1_x, p2_x), min(p1_y, p2_y),
    #                          abs(p1_x-p2_x), abs(p1_y-p2_y))
    #         self.update()
    #
    # def mouseReleaseEvent(self, event):
    #     if event.button() == Qt.LeftButton:
    #         p1_x, p1_y = self.lastPoint.x(), self.lastPoint.y()
    #         p2_x, p2_y = event.pos().x(), event.pos().y()
    #         lx, ly = min(p1_x, p2_x), min(p1_y, p2_y)
    #         w, h = abs(p1_x-p2_x), abs(p1_y-p2_y)
    #         if (p1_x, p1_y) != (p2_x, p2_y):
    #             if self.results and (len(self.results[-1]) == 4) \
    #                     and self.parent.autoLabel.text() == 'Manual Label':
    #                 self.showPopupOk('warning messege',
    #                                  'Please mark the box you drew.')
    #                 self.pixmap = self.drawResultBox()
    #                 self.update()
    #             elif self.parent.autoLabel.text() == 'Auto Label':
    #                 self.results.append([lx, ly, lx+w, ly+h, self.last_idx])
    #                 for i, result in enumerate(self.results):
    #                     if len(result) == 4:  # fill empty labels
    #                         self.results[i].append(self.last_idx)
    #                 self.pixmap = self.drawResultBox()
    #                 self.update()
    #             else:
    #                 self.results.append([lx, ly, lx+w, ly+h])
    #             self.drawing = False

    def showPopupOk(self, title: str, content: str):
        msg = QMessageBox()
        msg.setWindowTitle(title)
        msg.setText(content)
        msg.setStandardButtons(QMessageBox.Ok)
        result = msg.exec_()
        if result == QMessageBox.Ok:
            msg.close()

    # def drawResultBox(self):
    #     res = QPixmap.copy(self.pixmapOriginal)
    #     painter = QPainter(res)
    #     font = QFont('mono', 15, 1)
    #     painter.setFont(font)
    #     painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
    #     for box in self.results:
    #         lx, ly, rx, ry = box[:4]
    #         painter.drawRect(lx, ly, rx-lx, ry-ly)
    #         if len(box) == 5:
    #             painter.setPen(QPen(Qt.blue, 2, Qt.SolidLine))
    #             painter.drawText(lx, ly+15, self.key_config[box[-1]])
    #             painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
    #     return res

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
        self.key_config = [
            config_dict['key_'+str(i)]
            for i in range(1, 10)
            if config_dict['key_'+str(i)]
        ]
        self.image_directory = None
        self.train_path = None
        self.obj_names_path = None
        self.categories = {}
        self.initUI()

    def initUI(self):
        # UI elements
        imagePathButton = QPushButton('Image Path (Folder)', self)
        trainPathButton = QPushButton('train.txt Path', self)
        objNamesPathButton = QPushButton('obj.names File Path', self)
        saveButton = QPushButton('Save', self)

        okButton = QPushButton('Next', self)
        cancelButton = QPushButton('Cancel', self)
        imagePathLabel = QLabel('Image Path not selected', self)
        trainPathLabel = QLabel('train.txt Path not selected', self)
        objNamesPathLabel = QLabel('obj.names Path not selected', self)
        saveLabel = QLabel('.', self)

        self.label_img = ImageWidget(self.parent, self.key_config)

        # Events
        okButton.clicked.connect(self.setNextImage)
        okButton.setEnabled(False)
        cancelButton.clicked.connect(self.label_img.cancelLast)
        imagePathButton.clicked.connect(
            lambda: self.registerImagePath(
                imagePathButton, imagePathLabel, okButton)
        )
        trainPathButton.clicked.connect(
            lambda: self.registerTrainPath(trainPathButton, trainPathLabel)
        )
        objNamesPathButton.clicked.connect(
            lambda: self.registerObjNamesPath(
                trainPathButton, objNamesPathLabel, okButton)
        )
        saveButton.clicked.connect(
            lambda: self.registerSavePath(
                saveButton, self.savePathLabel)
        )

        # Config Button
        hbox = QHBoxLayout()

        vbox = QVBoxLayout()
        vbox.addWidget(imagePathButton)
        vbox.addWidget(trainPathButton)
        vbox.addWidget(objNamesPathButton)
        vbox.addWidget(saveButton)
        hbox.addLayout(vbox)

        vbox = QVBoxLayout()
        vbox.addWidget(imagePathLabel)
        vbox.addWidget(trainPathLabel)
        vbox.addWidget(objNamesPathLabel)
        vbox.addWidget(saveLabel)
        hbox.addLayout(vbox)

        hbox.addStretch(3)
        hbox.addStretch(1)
        hbox.addWidget(okButton)
        hbox.addWidget(cancelButton)

        vbox = QVBoxLayout()
        vbox.addWidget(self.label_img)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

    def setNextImage(self, img=None):
        # if self.savePathLabel.text() == 'Results' and self.crop_mode:
        #     os.makedirs(self.save_directory, exist_ok=True)

        if not img:
            res = self.label_img.getResult()
            if res and len(res[-1]) != 5:
                self.label_img.showPopupOk('warning messege',
                                           'please mark the box you drew.')
                return 'Not Marked'
            self.writeResults(res)
            self.label_img.resetResult()
            try:
                self.currentImg = self.imgList.pop(0)
                self.currentCfg = self.imgListCfg.pop(0)
            except Exception:
                self.currentImg = 'end.png'
                self.currentCfg = ''
        else:
            self.label_img.resetResult()

        try:
            im = Image.open(self.currentImg)
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = dict(im.getexif().items())
            if exif[orientation] in [3, 6, 8]:
                im = im.transpose(Image.ROTATE_180)
                im.save(self.currentImg)
        except Exception:
            pass

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

    def enableOkButton(self, okButton):
        if self.image_directory and self.obj_names_path:
            okButton.setEnabled(True)
        else:
            okButton.setEnabled(False)
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
                # if self.crop_mode:
                #     img = cv2.imread(self.currentImg)
                #     if img is None:
                #         n = np.fromfile(self.currentImg, np.uint8)
                #         img = cv2.imdecode(n, cv2.IMREAD_COLOR)
                #     oh, ow = img.shape[:2]
                #     w, h = round(yolo_format[3]*ow), round(yolo_format[4]*oh)
                #     x, y = round(yolo_format[1]*ow - w/2), round(yolo_format[2]*oh - h/2)
                #     crop_img = img[y:y+h, x:x+w]
                #     basename = os.path.basename(self.currentImg)
                #     filename = basename[:-4]+'-{}-{}.jpg'.format(self.key_config[idx], i)
                #
                #     # Korean dir support
                #     crop_img = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
                #     crop_img = Image.fromarray(crop_img)
                #     crop_img.save(os.path.join(
                #         self.save_directory, filename),
                #         dpi=(300, 300)
                #     )

    def registerSavePath(self, savePathButton, label):
        savePathButton.toggle()
        self.save_directory = str(QFileDialog.getExistingDirectory(
            self, "Select Save Directory")
        )
        basename = os.path.basename(self.save_directory)
        if basename:
            label.setText(basename+'/')
        else:
            print("Output Path not selected")
            self.save_directory = None

    def registerImagePath(self, imagePathButton, imagePathLabel, okButton):
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
        self.enableOkButton(okButton)

    def registerTrainPath(self, trainPathButton, trainPathLabel):
        trainPathButton.toggle()
        file_path = QFileDialog.getOpenFileName(
            self, "Select Train file", filter="*.txt")[0]
        file_name = os.path.basename(file_path)
        if not file_name:
            print("Train file Path not selected")
            return -1

        trainPathLabel.setText(file_name)
        self.train_path = file_name

        # Read Data
        with open(file_path, 'r') as f:
            paths = f.readlines()
            self.sample_paths = [
                x.replace('\n', '')
                for x in paths
            ]
        return

    def registerObjNamesPath(self, objNamesPathButton, objNamesPathLabel, okButton):
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
            self.key_config = [
                x.replace('\n', '')
                for x in obj_names
            ]
        self.enableOkButton(okButton)
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

    def keyPressEvent(self, e):
        config_len = len(self.key_config)
        for i, key_n in enumerate(range(49, 58), 1):
            if e.key() == key_n and config_len >= i:
                self.label_img.markBox(i-1)
                break
        if e.key() == Qt.Key_Escape:
            self.label_img.cancelLast()
        elif e.key() == Qt.Key_E:
            self.setNextImage()
        elif e.key() == Qt.Key_Q:
            self.label_img.resetResult()
            self.label_img.pixmap = self.label_img.drawResultBox()
            self.label_img.update()
        elif e.key() == Qt.Key_A:
            if self.parent.autoLabel.text() == 'Auto Label':
                self.parent.autoLabel.setText('Manual Label')
            else:
                self.parent.autoLabel.setText('Auto Label')


if __name__ == '__main__':
    csv.register_dialect('skip_space', skipinitialspace=True)
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())
