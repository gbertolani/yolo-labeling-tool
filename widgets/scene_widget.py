# -*- coding: utf-8 -*-

from PyQt5.QtCore import Qt, QRect
from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem, QDesktopWidget
from PyQt5.QtGui import QPen


class GraphicsScene(QGraphicsScene):
    pass
    # def __init__(self, x=None, y=None, width=None, height=None, parent=None):
    #     super(GraphicsRectItem, self).__init__(x=x, y=y, width=width,
    #                                            height=height, parent=parent)
    #     self.parent = parent
    #     self.setMouseTracking(True)
    #     self.screen_height = QDesktopWidget().screenGeometry().height()
    #     self.last_idx = 0
    #     # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    #     self.render()
    #
    # def render(self):
    #     self.pixmap = QPixmap.scaled(
    #         QPixmap('./resources/background/start.png'),
    #         640, 480,
    #         transformMode=Qt.SmoothTransformation
    #     )
    #     self.addPixmap(self.pixmap)
    #


    # def mouseMoveEvent(self, event):
    #     print("GP ", event)


class GraphicsRectItem(QGraphicsRectItem):

    def __init__(self, x, y, w, h, parent=None):
        super(GraphicsRectItem, self).__init__(x, y, w, h, parent=parent)
        self._pos_x = x
        self._pos_y = y
        self._w = w
        self._h = h
        self._color = Qt.magenta
        self._color_hover = Qt.black
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
        pen = QPen(Qt.black)
        pen.setWidth(1)
        painter.setPen(pen)
        self_rect = QRect(self._pos_x, self._pos_y, self._w, self._h)
        painter.drawText(self_rect, Qt.AlignLeft, "Hola")
        painter.restore()
        return res
