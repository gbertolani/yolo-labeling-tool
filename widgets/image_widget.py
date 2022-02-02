# -*- coding: utf-8 -*-

import csv

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QDesktopWidget, QMessageBox
from PyQt5.QtWidgets import QHBoxLayout, QLabel
from PyQt5.QtGui import QPixmap, QPainter, QPen, QFont, QColor
from PyQt5.QtCore import QPoint

from libs.samples import SampleGrouper, SampleObject


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
                                 str(sample.line_number))
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
