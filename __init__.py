# Copyright (c) 2023 5@xes
# Based on the TabPlus plugin  and licensed under LGPLv3 or higher.

VERSION_QT5 = False
try:
    from PyQt6.QtCore import QT_VERSION_STR
except ImportError:
    VERSION_QT5 = True
    
from . import SprueAntiWarping

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("sprueantiwarping")

def getMetaData():
    if not VERSION_QT5:
        QmlFile="qml_qt6/CustomTap.qml"
    else:
        QmlFile="qml_qt5/CustomTap.qml"
        
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Tab Plus"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Add Automatique Sprue"),
            "icon": "tool_icon.svg",
            "tool_panel": QmlFile,
            "weight": 11
        }
    }

def register(app):
    return { "tool": SprueAntiWarping.SprueAntiWarping() }
