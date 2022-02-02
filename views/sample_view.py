# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets


class GroupDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, parent=None):
        super(GroupDelegate, self).__init__(parent)
        self._plus_icon = QtGui.QIcon("./resources/icons/plus.png")
        self._minus_icon = QtGui.QIcon("./resources/icons/minus.png")

    def initStyleOption(self, option, index):
        super(GroupDelegate, self).initStyleOption(option, index)
        if not index.parent().isValid():
            is_open = bool(option.state & QtWidgets.QStyle.State_Open)
            option.features |= QtWidgets.QStyleOptionViewItem.HasDecoration
            option.icon = self._minus_icon if is_open else self._plus_icon


class GroupView(QtWidgets.QTreeView):

    def __init__(self, model, parent=None):
        super(GroupView, self).__init__(parent)
        self.setIndentation(0)
        self.setExpandsOnDoubleClick(False)
        self.clicked.connect(self.on_clicked)
        delegate = GroupDelegate(self)
        self.setItemDelegateForColumn(0, delegate)
        self.setModel(model)
        self.header().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeToContents
        )
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def on_clicked(self, index):
        if not index.parent().isValid() and index.column() == 0:
            self.setExpanded(index, not self.isExpanded(index))


class GroupModel(QtGui.QStandardItemModel):

    def __init__(self, parent=None):
        super(GroupModel, self).__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["", "Name", "New Category", "Delete"])
        for i in range(self.columnCount()):
            self.horizontalHeaderItem(i)
        self.category_icon = QtGui.QIcon("./resources/icons/category2.png")

    def add_group(self, idx, group_name):
        item_root = QtGui.QStandardItem()
        item_root.setEditable(False)
        item = QtGui.QStandardItem(group_name + " [%s]" % str(idx))
        item.setEditable(False)
        item.setCheckable(True)
        item.setCheckState(QtCore.Qt.CheckState(2))
        item.setData(idx)
        item.setData(item_root, 3)
        ii = self.invisibleRootItem()
        i = ii.rowCount()
        for j, it in enumerate((item_root, item)):
            ii.setChild(i, j, it)
            ii.setEditable(False)
        for j in range(self.columnCount()):
            it = ii.child(i, j)
            if it is None:
                it = QtGui.QStandardItem()
                ii.setChild(i, j, it)
        return item_root

    def append_element_to_group(self, group_item, sample):
        j = group_item.rowCount()
        item = QtGui.QStandardItem()
        item.setEditable(False)
        group_item.setChild(j, 0, item)
        item_label = sample.category_name + "_" + str(sample.line_number)
        item = QtGui.QStandardItem(item_label)
        group_item.setChild(j, 1, item)
        item.setEditable(True)
        item.setCheckable(True)
        item.setData(sample)
        checked_state = 2 if sample.isVisible() else 0
        item.setCheckState(QtCore.Qt.CheckState(checked_state))
        item_icon = QtGui.QStandardItem()
        item_icon.setEditable(True)
        item_icon.setIcon(self.category_icon)
        item_icon.setData(sample)
        group_item.setChild(j, 2, item_icon)
        item_rm = QtGui.QStandardItem()
        item_rm.setEditable(True)
        item_rm.setData(sample)
        item_rm.setCheckable(True)
        group_item.setChild(j, 3, item_rm)
