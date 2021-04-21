# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GeoDataDialog
                                 A QGIS plugin
 This plugin gathers cz/sk data sources.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2020-08-04
        git sha              : $Format:%H$
        copyright            : (C) 2020 by Test
        email                : test
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import configparser
import sys
import webbrowser

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.PyQt import QtGui
from qgis.utils import iface
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import *

from .crs_trans.CoordinateTransformation import CoordinateTransformation
from .crs_trans.CoordinateTransformationList import CoordinateTransformationList
from .crs_trans.ShiftGrid import ShiftGrid
from .crs_trans.ShiftGridList import ShiftGridList

from .Geo_Data_dialog import GeoDataDialog

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'Region_dialog_base.ui'))


class RegionDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None, start=True):
        """Constructor."""
        super(RegionDialog, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)
        self.start = start
        self.pushButtonSVK.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/svk.png")))
        self.pushButtonCZE.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/cze.png")))
        self.pushButtonSVK.clicked.connect(self.setRegionSVK)
        self.pushButtonCZE.clicked.connect(self.setRegionCZE)

        self.grids = ShiftGridList()
        self.load_shift_grids()
        self.transformations = CoordinateTransformationList()
        self.load_crs_transformations()

    def setStart(self, start):
        self.start = start

    def setRegion(self, region):
        self.transformations.applyTransforations(region)
        QMessageBox.information(None, QApplication.translate("GeoData", "Info", None),
                                QApplication.translate("GeoData", "You have to restart QGIS to apply all settings.", None))
        s = QgsSettings()
        s.setValue("geodata_cz_sk/region", region)
        if self.start:
            self.hide()
            gdd = GeoDataDialog(self.iface)
            gdd.show()
            gdd.exec_()
        else:
            self.hide()

    def setRegionSVK(self):
        self.setRegion("SVK")

    def setRegionCZE(self):
        self.setRegion("CZE")

    def load_crs_transformations(self):
        """
        Loads available transformatios defined in crs_trans.ini
        """

        projVersion = QgsProjUtils.projVersionMajor()

        transConfigFile = os.path.join(os.path.dirname(__file__), "crs_trans", "crs_trans.ini")
        transConfig = configparser.ConfigParser()

        try:
            transConfig.read(transConfigFile)
        except Exception:
            self.iface.messageBar().pushMessage(QApplication.translate("GeoData", "Error", None),
                                                QApplication.translate("GeoData", "Unable to read coordinate transformations definition file.", None),
                                                level=Qgis.Critical)
            raise Exception("Unable to read coordinate transformations definition file.")

        for transSection in transConfig:
            if transSection != "DEFAULT":
                transSectionContent = transConfig[transSection]

                regions = transSectionContent.get("Regions", None)
                if isinstance(regions, str) and regions is not None:
                    regions = regions.split(" ")
                crsFrom = transSectionContent.get("CrsFrom")
                crsTo = transSectionContent.get("CrsTo")

                # TransfOld is used only for Proj version 6 and only if present
                if projVersion == 6 and "TransfOld" in [x[0] for x in transConfig.items(transSection)]:
                    transformation = transSectionContent.get("TransfOld")
                else:
                    transformation = transSectionContent.get("Transf")

                if projVersion == 6:
                    grid = transSectionContent.get("GridOld", None)
                else:
                    grid = transSectionContent.get("Grid", None)

                if grid is not None and len(self.grids.getGridsByKeys(grid)) != 1:
                    self.iface.messageBar().pushMessage(QApplication.translate("GeoData", "Warning", None),
                                                        QApplication.translate("GeoData", "Skipping definition section {} because grid {} is unknown.".format(transSection, grid), None),
                                                        level=Qgis.Warning,
                                                        duration=5)
                    continue

                # print("--------------------\nSection: {}\nRegion: {}\nCrsFrom: {}\nCrsTo: {}\nTransformation: {}\nShiftFile: {}".format(
                #     transSection, regions, crsFrom, crsTo, transformation, gridFileUrl))

                if regions is None or regions == "" or \
                   crsFrom is None or crsFrom == "" or \
                   crsTo is None or crsTo == "" or \
                   transformation is None or transformation == "":
                    self.iface.messageBar().pushMessage(QApplication.translate("GeoData", "Warning", None),
                                                        QApplication.translate("GeoData", "Skipping incomplete transformation definition section {}.".format(transSection), None),
                                                        level=Qgis.Warning,
                                                        duration=5)
                    continue

                try:
                    transf = CoordinateTransformation(regions, crsFrom, crsTo, transformation, self.grids, grid)
                    self.transformations.append(transf)
                except Exception:
                    continue

    def load_shift_grids(self):
        """
        Loads available shift grids defined in grids.ini
        """

        gridsConfigFile = os.path.join(os.path.dirname(__file__), "crs_trans", "grids.ini")
        gridsConfig = configparser.ConfigParser()

        try:
            gridsConfig.read(gridsConfigFile)
        except Exception:
            self.iface.messageBar().pushMessage(QApplication.translate("GeoData", "Error", None),
                                                QApplication.translate("GeoData", "Unable to read grids definition file.", None),
                                                level=Qgis.Critical)
            raise Exception("Unable to read grids definition file.")

        for grid in gridsConfig:
            if grid != "DEFAULT":
                gridContent = gridsConfig[grid]

                gridFileUrl = gridContent.get("GridFileUrl")
                gridFileName = gridContent.get("GridFileName")

                if gridFileUrl is None or gridFileName is None:
                    self.iface.messageBar().pushMessage(QApplication.translate("GeoData", "Warning", None),
                                                        QApplication.translate("GeoData", "Skipping grid definition of grid {}.".format(grid), None),
                                                        level=Qgis.Warning,
                                                        duration=5)
                    continue

                try:
                    shiftGrid = ShiftGrid(grid, gridFileUrl, gridFileName)
                    self.grids.append(shiftGrid)
                except Exception:
                    continue