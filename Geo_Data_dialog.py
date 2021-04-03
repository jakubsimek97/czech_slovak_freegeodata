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

import importlib, inspect
from .data_sources.source import Source
from .crs_trans.CoordinateTransformation import CoordinateTransformation
from .crs_trans.CoordinateTransformationList import CoordinateTransformationList
from .crs_trans.ShiftGrid import ShiftGrid
from .crs_trans.ShiftGridList import ShiftGridList

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'Geo_Data_dialog_base.ui'))


class GeoDataDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface, regiondialog, parent=None):
        """Constructor."""
        super(GeoDataDialog, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)
        self.dlg_region = regiondialog
        # self.pushButtonAbout.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/cropped-opengeolabs-logo-small.png")))
        # self.pushButtonAbout.clicked.connect(self.showAbout)
        self.pushButtonLoadRuianPlugin.clicked.connect(self.load_ruian_plugin)
        self.pushButtonLoadData.clicked.connect(self.load_data)
        self.pushButtonSourceOptions.clicked.connect(self.show_source_options_dialog)
        self.pushButtonSettings.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icons/settings.png")))
        self.pushButtonSettings.clicked.connect(self.show_settings)
        self.data_sources = []
        self.treeWidgetSources.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeWidgetSources.customContextMenuRequested.connect(self.open_context_menu)
        self.load_sources_into_tree()
        self.selectedSource = -1

        self.grids = ShiftGridList()
        self.load_shift_grids()
        self.transformations = CoordinateTransformationList()
        self.load_crs_transformations()

    def get_url(self, config):
        if config['general']['type'] == 'WMS':
            # TODO check CRS? Maybe.
            url = 'url=' + config['wms']['url']
            layers = config['wms']['layers'].split(',')
            for layer in layers:
                url += "&layers=" + layer
            styles = config['wms']['styles'].split(',')
            for style in styles:
                url += "&styles=" + style
            url += "&" + config['wms']['params']
            return url

        if config['general']['type'] == 'TMS':
            return "type=xyz&url=" + config['tms']['url']

    def load_data(self):
        # print("LOAD DATA")
        for data_source in self.data_sources:
            # print(data_source)
            if data_source['checked'] == "True":
                if "WMS" in data_source['type'] or "TMS" in data_source['type']:
                    self.add_layer(data_source)
                    self.addSourceToBrowser(data_source)
                if "PROC" in data_source['type']:
                    if data_source['proc_class'] is not None:
                        self.add_proc_data_source_layer(data_source)

    def load_sources_into_tree(self):

        self.treeWidgetSources.itemChanged.connect(self.handleChanged)
        self.treeWidgetSources.itemSelectionChanged.connect(self.handleSelected)
        tree    = self.treeWidgetSources
        paths = []

        current_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        sources_dir = os.path.join(current_dir, 'data_sources')

        for name in os.listdir(sources_dir):
            if os.path.isdir(os.path.join(sources_dir, name)) and name[:2] != "__":
                paths.append(name)

        paths.sort()
        config = configparser.ConfigParser()
        group = ""

        index = 0

        for path in paths:
            config.read(os.path.join(sources_dir, path, 'metadata.ini'))
            current_group = path.split("_")[0]
            if current_group != group:
                group = current_group
                parent = QTreeWidgetItem(tree)
                parent.setText(0, current_group) # TODO read from metadata.ini (maybe)
                parent.setFlags(parent.flags()
                  | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)

            url = ""
            if "WMS" in config['general']['type'] or "TMS" in config['general']['type']:
                url = self.get_url(config)

            proc_class = None
            if "PROC" in config['general']['type']:
                proc_class = self.get_proc_class(path)

            self.data_sources.append(
                {
                    "type": config['general']['type'],
                    "alias": config['ui']['alias'],
                    "url": url,
                    "checked": config['ui']['checked'],
                    "proc_class": proc_class
                }
            )
            child = QTreeWidgetItem(parent)
            child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
            child.setText(0, config['ui']['alias'])
            child.setIcon(0, QIcon(os.path.join(sources_dir, path, config['ui']['icon'])))
            parent.setIcon(0, QIcon(os.path.join(sources_dir, path, config['ui']['icon'])))
            child.setData(0, Qt.UserRole, index)
            if config['ui']['checked'] == "True":
                child.setCheckState(0, Qt.Checked)
            else:
                child.setCheckState(0, Qt.Unchecked)
            index += 1

    def handleSelected(self):
        self.selectedSource = -1
        self.pushButtonSourceOptions.setEnabled(False)
        print(self.treeWidgetSources.selectedItems())
        for item in self.treeWidgetSources.selectedItems():
            if item.data(0, Qt.UserRole) is not None:
                id = int(item.data(0, Qt.UserRole))
                # print(str(id))
                # print(self.data_sources[id])
                if self.data_sources[id]['proc_class'] is not None and self.data_sources[id]['proc_class'].has_options_dialog():
                    self.selectedSource = id
                    self.pushButtonSourceOptions.setEnabled(True)
                    # print("HAS OPTIONS DIALOG")

    def handleChanged(self, item, column):
        # Get his status when the check status changes.
        if item.data(0, Qt.UserRole) is not None:
            id = int(item.data(0, Qt.UserRole))
            if item.checkState(column) == Qt.Checked:
                # print("checked", item, item.text(column))
                self.data_sources[id]['checked'] = "True"
            if item.checkState(column) == Qt.Unchecked:
                # print("unchecked", item, item.text(column))
                self.data_sources[id]['checked'] = "False"
            # print(item.data(0, Qt.UserRole))

    def open_context_menu(self):
        # TODO - if we want context menu
        # https://wiki.python.org/moin/PyQt/Creating%20a%20context%20menu%20for%20a%20tree%20view
        print("MENU")

    def show_source_options_dialog(self):
        if self.selectedSource >= 0:
            self.data_sources[self.selectedSource]['proc_class'].show_options_dialog()

    def add_layer(self, data_source):
        # print("Add Layer " + (self.wms_sources[index]))
        # rlayer = QgsRasterLayer(self.wms_sources[index], 'MA-ALUS', 'wms')
        print(data_source['url'])
        layer = QgsRasterLayer(data_source['url'], data_source['alias'], 'wms')
        # TODO check if the layer is valid
        QgsProject.instance().addMapLayer(layer)

    def get_proc_class(self, path):
        current_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        current_module_name = os.path.splitext(os.path.basename(current_dir))[0]
        module = importlib.import_module(".data_sources." + path + ".source", package=current_module_name)
        for member in dir(module):
            if member != 'Source':
                handler_class = getattr(module, member)
                # if member == 'SampleOne':
                #     print("GPC")
                #     print(handler_class)
                #     print(inspect.isclass(handler_class))
                #     print(issubclass(handler_class, Source))
                if handler_class and inspect.isclass(handler_class) and issubclass(handler_class, Source):
                    current_source = handler_class()
                    return current_source
        return None

    def addSourceToBrowser(self, data_source):
        source = None
        if data_source['type'] == "TMS":
            url = data_source['url'][13:]
            source = ["connections-xyz", data_source['alias'], "", "", "", url, "", "19", "0"]
        if data_source['type'] == "WMS":
            url = data_source['url'][4:].split("&")[0]
            source = ["connections-wms", data_source['alias'], "", "", "", url, "", "19", "0"]
        if source != None:
            connectionType = source[0]
            connectionName = source[1]
            QSettings().setValue("qgis/%s/%s/authcfg" % (connectionType, connectionName), source[2])
            QSettings().setValue("qgis/%s/%s/password" % (connectionType, connectionName), source[3])
            QSettings().setValue("qgis/%s/%s/referer" % (connectionType, connectionName), source[4])
            QSettings().setValue("qgis/%s/%s/url" % (connectionType, connectionName), source[5])
            QSettings().setValue("qgis/%s/%s/username" % (connectionType, connectionName), source[6])
            QSettings().setValue("qgis/%s/%s/zmax" % (connectionType, connectionName), source[7])
            QSettings().setValue("qgis/%s/%s/zmin" % (connectionType, connectionName), source[8])

        iface.reloadConnections()

    def add_proc_data_source_layer(self, data_source):
        if data_source['type'] == "PROC_VEC":
            data_source['proc_class'].set_iface(self.iface)
            layer = data_source['proc_class'].get_vector(self.get_extent(), self.get_epsg())
        if data_source['type'] == "PROC_RAS":
            data_source['proc_class'].set_iface(self.iface)
            layer = data_source['proc_class'].get_raster(self.get_extent(), self.get_epsg())
        if layer is not None:
            QgsProject.instance().addMapLayer(layer)

    def get_extent(self):
        return self.iface.mapCanvas().extent()

    def get_epsg(self):
        srs = self.iface.mapCanvas().mapSettings().destinationCrs()
        return srs.authid()

    def load_ruian_plugin(self):
        ruian_found = False
        for x in iface.mainWindow().findChildren(QAction):
            if "RUIAN" in x.toolTip():
                ruian_found = True
                x.trigger()

        if not ruian_found:
            self.labelRuianError.setText(QApplication.translate("GeoData","This functionality requires RUIAN plugin", None))

    # def showAbout(self):
    #     try:
    #         webbrowser.get().open("http://opengeolabs.cz")
    #     except (webbrowser.Error):
    #         self.iface.messageBar().pushMessage(QApplication.translate("GeoData", "Error", None), QApplication.translate("GeoData", "Can not find web browser to open page about", None), level=Qgis.Critical)

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

    def show_settings(self):
        self.dlg_region.setStart(False)
        self.dlg_region.show()
        # Run the dialog event loop
        result = self.dlg_region.exec_()
