# -*- coding: utf-8 -*-

import csv
from glob import glob
import os
import re
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QFileDialog, QLabel
from PyQt5.QtWidgets import QMessageBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem,QGraphicsItem
from PyQt5.QtGui import QColor, QIcon, QPen, QPixmap


from libs.samples import SampleObject
from views.sample_view import GroupModel, GroupView
from widgets.image_widget import ImageWidget
from widgets.scene_widget import GraphicsScene, GraphicsRectItem


class MyApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('./resources/icons/icon.png'))
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
        self._on_refresh = True
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
        self._on_refresh = False
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
            if item.column() == 3:
                if bool(item.checkState()):
                    item_data.setDeleted()
                else:
                    item_data.setDeleted(deleted=False)
            else:
                if self._on_refresh:
                    item.setCheckState(2)
                    item_data.setVisible()
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

        # self.label_img = ImageWidget(self.parent)
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
        # hbox_1.addWidget(self.label_img, 7)

        self.zoom = 0
        self.grview = QGraphicsView()
        self.label_img = GraphicsScene(parent=self.parent)
        self.grview.setScene(self.label_img)
        self.grview.setAlignment(Qt.AlignCenter)
        self.grview.fitInView(self.label_img.sceneRect())
        self.grview.setBackgroundBrush(Qt.black)


        # scene = GraphicsScene()
        # self.zoom = 0
        # self.grview.setScene(scene)
        # # self.grview.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        # self.grview.setAlignment(Qt.AlignCenter)
        #
        # item = GraphicsRectItem(640, 480, 40, 40,)
        #
        # pen = QPen(Qt.magenta)
        # pen.setWidth(8)
        # item.setPen(pen)
        #
        #
        # # item.setFlag(QGraphicsItem.ItemIsMovable)
        # scene.addItem(item)
        # self.grview.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)

        hbox_1.addWidget(self.grview, 7)

        self.group_model = GroupModel(self)
        self.tree_view = GroupView(self.group_model)
        hbox_1.addWidget(self.tree_view, 3)
        vbox.addLayout(hbox_1)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

    def wheelEvent(self, event):
        scale_factor = 1.15
        print(event.angleDelta())
        self.zoom += event.angleDelta().y()/ (2 * abs(event.angleDelta().y()))
        if event.angleDelta().y() > 0:
            a = self.grview.scale(scale_factor, scale_factor)
        else:
            a = self.grview.scale(1 / scale_factor, 1/ scale_factor)
        print(a)

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
        # self.parent.fitSize()
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
                    if sample.isDeleted():
                        continue
                    writer = csv.writer(file, delimiter=' ',
                                        dialect='skip_space')
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
        self._imgList = []
        for t in types:
            self._imgList.extend(glob(directory+'/'+t))
        # Sort img List
        self._imgList.sort()

        self.imgListCfg = []
        self.imgList = []
        for img_path in self._imgList:
            txt_path = re.sub('.png$', '.txt', img_path)
            if os.path.exists(txt_path) and txt_path != img_path:
                self.imgListCfg.append(txt_path)
                self.imgList.append(img_path)
        self.total_imgs = len(self.imgList)
        print("Total images with text found: ", str(self.total_imgs))
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
