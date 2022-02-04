# -*- coding: utf-8 -*-

import csv

from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem, \
        QDesktopWidget
from PyQt5.QtGui import QPen, QPixmap, QColor

from libs.samples import SampleGrouper, SampleObject

# class GraphicsView(QGraphicsView):


class GraphicsScene(QGraphicsScene):

    def __init__(self, parent=None):
        super(GraphicsScene, self).__init__(parent=parent)
        self.parent = parent
        # self.setMouseTracking(True)
        self.screen_height = QDesktopWidget().screenGeometry().height()
        self.screen_width = QDesktopWidget().screenGeometry().width()
        self.last_idx = 0
        self.border_pen = QPen(Qt.blue)
        self.border_pen.setWidth(8)

        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.render()

    def render(self):
        # Add Border
        # border = GraphicsRectItem(0, 0, self.screen_width, self.screen_height)
        # border.setPen(self.border_pen)
        # self.addItem(border)
        # Add Bg
        self.pixmap = QPixmap.scaled(
            QPixmap('./resources/background/start.png'),
            self.screen_width, self.screen_height,
            transformMode=Qt.SmoothTransformation
        )
        self.addPixmap(self.pixmap)
        self.pixmapOriginal = QPixmap.copy(self.pixmap)
        self.drawing = False
        self.lastPoint = QPoint()
        self.setSceneRect(0, 0, self.screen_width, self.screen_height)

    def drawSamplesBox(self):
        # Delete all items and re-draw samples

        res = QPixmap.copy(self.pixmapOriginal)
        # Drawing by groups
        groups = self.grouper.getSamplesGrouped(only_visible=True)
        for gindex, samples in groups.items():
            gcolor = self.grouper.categories_color[gindex]
            qcolor = QColor(*gcolor)
            for sample in samples:
                item = GraphicsRectItem(
                    sample.lx, sample.ly,
                    sample.rx - sample.lx,
                    sample.ry - sample.ly,
                    color=qcolor,
                    text=str(sample.line_number),
                    text_color=Qt.blue
                )
                self.addItem(item)
        return res

    def setPixmap(self, image_fn):
        print(image_fn)
        self.clear()
        self.pixmap = QPixmap(image_fn)
        self.W, self.H = self.pixmap.width(), self.pixmap.height()

        if self.H > self.screen_height * 0.8:
            resize_ratio = (self.screen_height * 0.8) / self.H
            self.W = round(self.W * resize_ratio)
            self.H = round(self.H * resize_ratio)
            self.pixmap = QPixmap.scaled(self.pixmap, self.W, self.H,
                                         transformMode=Qt.SmoothTransformation)

        self.parent.imageSize.setText('{}x{}'.format(self.W, self.H))
        # self.setFixedSize(self.W, self.H)
        self.pixmapOriginal = QPixmap.copy(self.pixmap)
        self.addPixmap(self.pixmap)
        # Resize scene:
        self.setSceneRect(0, 0, self.W, self.H)
        self.parent.mainWidget.grview.setAlignment(Qt.AlignCenter)
        self.parent.mainWidget.grview.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

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


class GraphicsRectItem(QGraphicsRectItem):

    def __init__(self, x, y, w, h, parent=None, color=Qt.magenta,
                 text='', text_color=Qt.black):
        super(GraphicsRectItem, self).__init__(x, y, w, h, parent=parent)
        self._pos_x = x
        self._pos_y = y
        self._w = w
        self._h = h
        self._color = color
        self._color_hover = Qt.black
        self.text = text
        self.text_color = text_color
        self.setAcceptHoverEvents(True)
        self.pen = QPen(self._color)
        self.pen.setWidth(1)
        self.setPen(self.pen)

    def hoverEnterEvent(self, event):
        self.pen.setColor(self._color_hover)
        self.setPen(self.pen)
        self.setRect(self._pos_x, self._pos_y, self._w, self._h)
        print('inside')

    def hoverLeaveEvent(self, event):
        self.pen.setColor(self._color)
        self.setPen(self.pen)
        self.setRect(self._pos_x, self._pos_y, self._w, self._h)
        self.isVisibleTo
        print('outside')

    def mouseMoveEvent(self, event):
        print("ITEM ", event)
        return super().mouseMoveEvent(event)

    def paint(self, painter, option, widget=None):
        res = super(GraphicsRectItem, self).paint(painter, option,
                                                  widget=widget)
        painter.save()
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        pen = QPen(self.text_color)
        pen.setWidth(1)
        painter.setPen(pen)
        self_rect = QRect(self._pos_x, self._pos_y, self._w, self._h)
        painter.drawText(self_rect, Qt.AlignLeft, self.text)
        painter.restore()
        return res
