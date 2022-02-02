# -*- coding: utf-8 -*-

import math
import numpy as np


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
        self._deleted = False

    def _truncate(self, number):
        """
        Returns a value truncated to a specific
        number of decimal places.
        """
        factor = 10.0 ** 6
        number += 0.0000001  # Sum lost decimals
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

    def setDeleted(self, deleted=True):
        self._deleted = deleted
        return True

    def isDeleted(self):
        return self._deleted

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
