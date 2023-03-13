# Copyright (c) 2023 5@xes
# Based on the TabPlus plugin  and licensed under LGPLv3 or higher.

VERSION_QT5 = False
try:
    from PyQt6.QtCore import QT_VERSION_STR
except ImportError:
    VERSION_QT5 = True
    
from . import SpoonAntiWarping

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("spoonantiwarping")

def getMetaData():
    if not VERSION_QT5:
        QmlFile="qml/qml_qt6/CustomSpoon.qml"
    else:
        QmlFile="qml/qml_qt5/CustomSpoon.qml"
        
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Spoon Anti-Warping"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Add Automatique Anti-Warping Spoon"),
            "icon": "tool_icon.svg",
            "tool_panel": QmlFile,
            "weight": 11
        }
    }

def register(app):
    return { "tool": SpoonAntiWarping.SpoonAntiWarping() }
