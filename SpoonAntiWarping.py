#--------------------------------------------------------------------------------------------
# Copyright (c) 2023 5@xes
#--------------------------------------------------------------------------------------------
# Based on the TabPlus plugin by 5@xes, and licensed under LGPLv3 or higher.
#
#  https://github.com/5axes/TabPlus
#
# All modification 5@xes
# First release  22-01-2023  First proof of concept
# Second release  23-01-2023  Limit the number of Tab with Circular element
#------------------------------------------------------------------------------------------------------------------

VERSION_QT5 = False
try:
    from PyQt6.QtCore import Qt, QTimer, pyqtProperty, pyqtSignal, pyqtSlot, QUrl
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PyQt5.QtCore import Qt, QTimer, pyqtProperty, pyqtSignal, pyqtSlot, QUrl
    from PyQt5.QtWidgets import QApplication
    VERSION_QT5 = True

from typing import Optional, List

from cura.CuraApplication import CuraApplication

from UM.Resources import Resources
from UM.Logger import Logger
from UM.Message import Message
from UM.Math.Vector import Vector
from UM.Tool import Tool
from UM.Event import Event, MouseEvent
from UM.Mesh.MeshBuilder import MeshBuilder

from cura.PickingPass import PickingPass

from UM.Settings.SettingDefinition import SettingDefinition
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Settings.ContainerRegistry import ContainerRegistry

from collections import OrderedDict

from cura.CuraVersion import CuraVersion  # type: ignore
from UM.Version import Version

from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from cura.Operations.SetParentOperation import SetParentOperation

from UM.Settings.SettingInstance import SettingInstance

from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Scene.ToolHandle import ToolHandle
from UM.Tool import Tool

import os.path 
import math
import numpy as np

from UM.Resources import Resources
from UM.i18n import i18nCatalog

i18n_cura_catalog = i18nCatalog("cura")
i18n_catalog = i18nCatalog("fdmprinter.def.json")
i18n_extrud_catalog = i18nCatalog("fdmextruder.def.json")

Resources.addSearchPath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)))
)  # Plugin translation file import

catalog = i18nCatalog("spoonantiwarping")

if catalog.hasTranslationLoaded():
    Logger.log("i", "Spoon Anti-Warping Plugin translation loaded!")
   
class SpoonAntiWarping(Tool):
    def __init__(self):
        super().__init__()
        
        # Stock Data  
        self._all_picked_node = []
        
        # variable for menu dialog        
        self._UseSize = 10.0
        self._UseLength = 3.0
        self._UseWidth = 2.0
        self._Nb_Layer = 1
        self._SMsg = catalog.i18nc("@message", "Remove All") 

        # Shortcut
        if not VERSION_QT5:
            self._shortcut_key = Qt.Key.Key_S
        else:
            self._shortcut_key = Qt.Key_S
            
        self._controller = self.getController()

        self._selection_pass = None
        
        self._application = CuraApplication.getInstance()
        #important do not delete
        self._i18n_catalog = None

        # Suggested solution from fieldOfView . in this discussion solved in Cura 4.9
        # https://github.com/5axes/Calibration-Shapes/issues/1
        # Cura are able to find the scripts from inside the plugin folder if the scripts are into a folder named resources
        # V1.1.1 Already added for Translation .. Don't need More SearchPath
        # Resources.addSearchPath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources"))        
        
        self.Major=1
        self.Minor=0
        
        # Test version for Cura Master
        # https://github.com/smartavionics/Cura
        if "master" in CuraVersion :
            self.Major=4
            self.Minor=20
        else:
            try:
                self.Major = int(CuraVersion.split(".")[0])
                self.Minor = int(CuraVersion.split(".")[1])
            except:
                pass
        
        self.setExposedProperties("SSize", "SLength", "SWidth", "NLayer", "SMsg" )
        
        CuraApplication.getInstance().globalContainerStackChanged.connect(self._updateEnabled)
         
        # Note: if the selection is cleared with this tool active, there is no way to switch to
        # another tool than to reselect an object (by clicking it) because the tool buttons in the
        # toolbar will have been disabled. That is why we need to ignore the first press event
        # after the selection has been cleared.
        Selection.selectionChanged.connect(self._onSelectionChanged)
        self._had_selection = False
        self._skip_press = False

        self._had_selection_timer = QTimer()
        self._had_selection_timer.setInterval(0)
        self._had_selection_timer.setSingleShot(True)
        self._had_selection_timer.timeout.connect(self._selectionChangeDelay)
        
        # set the preferences to store the default value
        self._preferences = CuraApplication.getInstance().getPreferences()
        self._preferences.addPreference("spoon_anti_warping/s_size", 10)
        # convert as float to avoid further issue
        self._UseSize = float(self._preferences.getValue("spoon_anti_warping/s_size"))
 
        self._preferences.addPreference("spoon_anti_warping/s_length", 3)
        # convert as float to avoid further issue
        self._UseLength = float(self._preferences.getValue("spoon_anti_warping/s_length"))

        self._preferences.addPreference("spoon_anti_warping/s_width", 2)
        # convert as float to avoid further issue
        self._UseWidth = float(self._preferences.getValue("spoon_anti_warping/s_width"))

        self._preferences.addPreference("spoon_anti_warping/nb_layer", 1)
        # convert as float to avoid further issue
        self._Nb_Layer = int(self._preferences.getValue("spoon_anti_warping/nb_layer"))       

        # Define a new settings "spoon_mesh""
        self._settings_dict = OrderedDict()
        self._settings_dict["spoon_mesh"] = {
            "label": "Spoon mesh",
            "description": "Mesh used as spoon identification element (Special parameter added for the plugin Spoon Anti-Warping!)",
            "type": "bool",
            "default_value": False,
            "enabled": True,
            "settable_per_mesh": True,
            "settable_per_extruder": False,
            "settable_per_meshgroup": False,
            "settable_globally": False
        }
        ContainerRegistry.getInstance().containerLoadComplete.connect(self._onContainerLoadComplete)
        
        Logger.log('d', "Info CuraVersion --> " + str(CuraVersion))
                
    def event(self, event):
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
        if not VERSION_QT5:
            ctrl_is_active = modifiers & Qt.KeyboardModifier.ControlModifier
        else:
            ctrl_is_active = modifiers & Qt.ControlModifier

        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons and self._controller.getToolsEnabled():
            if ctrl_is_active:
                self._controller.setActiveTool("TranslateTool")
                return

            if self._skip_press:
                # The selection was previously cleared, do not add/remove an support mesh but
                # use this click for selection and reactivating this tool only.
                self._skip_press = False
                return

            if self._selection_pass is None:
                # The selection renderpass is used to identify objects in the current view
                self._selection_pass = CuraApplication.getInstance().getRenderer().getRenderPass("selection")
            picked_node = self._controller.getScene().findObject(self._selection_pass.getIdAtPosition(event.x, event.y))
            if not picked_node:
                # There is no slicable object at the picked location
                return

            node_stack = picked_node.callDecoration("getStack")

            
            if node_stack: 
                if node_stack.getProperty("spoon_mesh", "value"):
                    self._removeSpoonMesh(picked_node)
                    return

                elif node_stack.getProperty("anti_overhang_mesh", "value") or node_stack.getProperty("infill_mesh", "value") or node_stack.getProperty("support_mesh", "value"):
                    # Only "normal" meshes can have support_mesh added to them
                    return

            # Create a pass for picking a world-space location from the mouse location
            active_camera = self._controller.getScene().getActiveCamera()
            picking_pass = PickingPass(active_camera.getViewportWidth(), active_camera.getViewportHeight())
            picking_pass.render()

            picked_position = picking_pass.getPickedPosition(event.x, event.y)

            Logger.log('d', "X : {}".format(picked_position.x))
            Logger.log('d', "Y : {}".format(picked_position.y))
            Logger.log('d', "Name : {}".format(node_stack.getName()))
                            
            # Add the spoon_mesh at the picked location
            self._op = GroupedOperation()
            self._createSpoonMesh(picked_node, picked_position)
            self._op.push() 
           
    def _onContainerLoadComplete(self, container_id):
        if not ContainerRegistry.getInstance().isLoaded(container_id):
            # skip containers that could not be loaded, or subsequent findContainers() will cause an infinite loop
            return

        try:
            container = ContainerRegistry.getInstance().findContainers(id = container_id)[0]

        except IndexError:
            # the container no longer exists
            return

        if not isinstance(container, DefinitionContainer):
            # skip containers that are not definitions
            return
        if container.getMetaDataEntry("type") == "extruder":
            # skip extruder definitions
            return

        blackmagic_category = container.findDefinitions(key="blackmagic")
        spoon_mesh = container.findDefinitions(key=list(self._settings_dict.keys())[0])
        
        if blackmagic_category and not spoon_mesh:            
            blackmagic_category = blackmagic_category[0]
            for setting_key, setting_dict in self._settings_dict.items():

                definition = SettingDefinition(setting_key, container, blackmagic_category, self._i18n_catalog)
                definition.deserialize(setting_dict)

                # add the setting to the already existing platform adhesion setting definition
                blackmagic_category._children.append(definition)
                container._definition_cache[setting_key] = definition
                container._updateRelations(definition)
        
    def _createSpoonMesh(self, parent: CuraSceneNode, position: Vector):
        node = CuraSceneNode()
        EName = parent.getName()
        Logger.log('d', "Info createSpoonMesh for --> " + str(EName))
        
        Angle = self.defineAngle(EName,position)
        Logger.log('d', "Info createSpoonMesh Angle --> " + str(Angle))
        
        node.setName("RoundTab")
            
        node.setSelectable(True)
        
        # long=Support Height
        _long=position.y

        # get layer_height_0 used to define pastille height
        _id_ex=0
        
        # This function can be triggered in the middle of a machine change, so do not proceed if the machine change
        # has not done yet.
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        #extruder = global_container_stack.extruderList[int(_id_ex)] 
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]     
        self._Extruder_count=global_container_stack.getProperty("machine_extruder_count", "value") 
        #Logger.log('d', "Info Extruder_count --> " + str(self._Extruder_count))   
        
        _layer_h_i = extruder_stack.getProperty("layer_height_0", "value")
        _layer_height = extruder_stack.getProperty("layer_height", "value")
        _line_w = extruder_stack.getProperty("line_width", "value")
        # Logger.log('d', 'layer_height_0 : ' + str(_layer_h_i))
        _layer_h = (_layer_h_i * 1.2) + (_layer_height * (self._Nb_Layer -1) )
        _line_w = _line_w * 1.2 
        
        # Spoon creation Diameter , Length, Width, Increment angle 10°, length, layer_height_0*1.2
        mesh = self._createSpoon(self._UseSize,self._UseLength,self._UseWidth, 10,_long,_layer_h , Angle)
        
        node.setMeshData(mesh.build())

        active_build_plate = CuraApplication.getInstance().getMultiBuildPlateModel().activeBuildPlate
        node.addDecorator(BuildPlateDecorator(active_build_plate))
        node.addDecorator(SliceableObjectDecorator())

        stack = node.callDecoration("getStack") # created by SettingOverrideDecorator that is automatically added to CuraSceneNode
        settings = stack.getTop()

        definition = stack.getSettingDefinition("meshfix_union_all")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", False)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)
        
        definition = stack.getSettingDefinition("spoon_mesh")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", True)
        new_instance.resetState()  # Ensure that the state is not seen as a user state.
        settings.addInstance(new_instance)
        
        # Fix some settings in Cura to get a better result
        id_ex=0
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]
        #extruder = global_container_stack.extruderList[int(id_ex)]    
                
        #self._op = GroupedOperation()
        # First add node to the scene at the correct position/scale, before parenting, so the support mesh does not get scaled with the parent
        self._op.addOperation(AddSceneNodeOperation(node, self._controller.getScene().getRoot()))
        self._op.addOperation(SetParentOperation(node, parent))
        #op.push()
        node.setPosition(position, CuraSceneNode.TransformSpace.World)
        self._all_picked_node.append(node)
        self._SMsg = catalog.i18nc("@message", "Remove Last") 
        self.propertyChanged.emit()
        
        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _removeSpoonMesh(self, node: CuraSceneNode):
        parent = node.getParent()
        if parent == self._controller.getScene().getRoot():
            parent = None

        op = RemoveSceneNodeOperation(node)
        op.push()

        if parent and not Selection.isSelected(parent):
            Selection.add(parent)

        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)

    def _updateEnabled(self):
        plugin_enabled = False

        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        if global_container_stack:
            plugin_enabled = global_container_stack.getProperty("spoon_mesh", "enabled")

        CuraApplication.getInstance().getController().toolEnabledChanged.emit(self._plugin_id, plugin_enabled)
    
    def _onSelectionChanged(self):
        # When selection is passed from one object to another object, first the selection is cleared
        # and then it is set to the new object. We are only interested in the change from no selection
        # to a selection or vice-versa, not in a change from one object to another. A timer is used to
        # "merge" a possible clear/select action in a single frame
        if Selection.hasSelection() != self._had_selection:
            self._had_selection_timer.start()

    def _selectionChangeDelay(self):
        has_selection = Selection.hasSelection()
        if not has_selection and self._had_selection:
            self._skip_press = True
        else:
            self._skip_press = False

        self._had_selection = has_selection
 
        
    # SPOON creation
    def _createSpoon(self, size , length , width , nb , lg, He , angle):   
        mesh = MeshBuilder()
        # Per-vertex normals require duplication of vertices
        r = size / 2
        # First layer length
        sup = -lg + He
        l = -lg        
        
        rng = int(360 / nb)
        ang = math.radians(nb)
        
        verts = []
        
        # Add the handle of the spoon        
        s_sup = width / 2
        s_inf = s_sup
        
        """
        nbv=24 
        verts = [ # 6 faces with 4 corners each
            [-s_inf, l,  s_inf], [-s_sup,  sup,  s_sup], [ length,  sup,  s_sup], [ length, l,  s_inf],
            [-s_sup,  sup, -s_sup], [-s_inf, l, -s_inf], [ length, l, -s_inf], [ length,  sup, -s_sup],
            [ length, l, -s_inf], [-s_inf, l, -s_inf], [-s_inf, l,  s_inf], [ length, l,  s_inf],
            [-s_sup,  sup, -s_sup], [ length,  sup, -s_sup], [ length,  sup,  s_sup], [-s_sup,  sup,  s_sup],
            [-s_inf, l,  s_inf], [-s_inf, l, -s_inf], [-s_sup,  sup, -s_sup], [-s_sup,  sup,  s_sup],
            [ length, l, -s_inf], [ length, l,  s_inf], [ length,  sup,  s_sup], [ length,  sup, -s_sup]
        ]
        """
        nbv=20 
        verts = [ # 5 faces with 4 corners each
            [-s_inf, l,  s_inf], [-s_sup,  sup,  s_sup], [ length,  sup,  s_sup], [ length, l,  s_inf],
            [-s_sup,  sup, -s_sup], [-s_inf, l, -s_inf], [ length, l, -s_inf], [ length,  sup, -s_sup],
            [ length, l, -s_inf], [-s_inf, l, -s_inf], [-s_inf, l,  s_inf], [ length, l,  s_inf],
            [-s_sup,  sup, -s_sup], [ length,  sup, -s_sup], [ length,  sup,  s_sup], [-s_sup,  sup,  s_sup],
            [-s_inf, l,  s_inf], [-s_inf, l, -s_inf], [-s_sup,  sup, -s_sup], [-s_sup,  sup,  s_sup]
        ]               
        
        # Add Round Part of the Spoon
        nbvr = 0
        remain1 = 0
        remain2 = 0

        for i in range(0, rng):
            if (r*math.cos((i+1)*ang)) >= 0 or (abs(r*math.sin((i+1)*ang)) > s_sup and abs(r*math.sin(i*ang)) > s_sup)  :
                nbvr += 1
                # Top
                verts.append([length+r, sup, 0])
                verts.append([length+r+r*math.cos((i+1)*ang), sup, r*math.sin((i+1)*ang)])
                verts.append([length+r+r*math.cos(i*ang), sup, r*math.sin(i*ang)])
                #Side 1a
                verts.append([length+r+r*math.cos(i*ang), sup, r*math.sin(i*ang)])
                verts.append([length+r+r*math.cos((i+1)*ang), sup, r*math.sin((i+1)*ang)])
                verts.append([length+r+r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)])
                #Side 1b
                verts.append([length+r+r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)])
                verts.append([length+r+r*math.cos(i*ang), l, r*math.sin(i*ang)])
                verts.append([length+r+r*math.cos(i*ang), sup, r*math.sin(i*ang)])
                #Bottom 
                verts.append([length+r, l, 0])
                verts.append([length+r+r*math.cos(i*ang), l, r*math.sin(i*ang)])
                verts.append([length+r+r*math.cos((i+1)*ang), l, r*math.sin((i+1)*ang)])  
            else :
                if remain1 == 0 :
                    remain1 = i*ang
                    remain2 = 2*math.pi-remain1
                    
                    nbvr += 1
                    # Top
                    verts.append([length+r, sup, 0])
                    verts.append([length, sup, s_sup])
                    verts.append([length+r+r*math.cos(remain1), sup, r*math.sin(remain1)])
                    #Side 1a
                    verts.append([length+r+r*math.cos(remain1), sup, r*math.sin(remain1)])
                    verts.append([length, sup, s_sup])
                    verts.append([length, l, s_inf])
                    #Side 1b
                    verts.append([length, l, s_inf])
                    verts.append([length+r+r*math.cos(remain1), l, r*math.sin(remain1)])
                    verts.append([length+r+r*math.cos(remain1), sup, r*math.sin(remain1)])
                    #Bottom 
                    verts.append([length+r, l, 0])
                    verts.append([length+r+r*math.cos(remain1), l, r*math.sin(remain1)])
                    verts.append([length, l, s_inf])  
                    
                    nbvr += 1 
                    # Top
                    verts.append([length+r, sup, 0])
                    verts.append([length+r+r*math.cos(remain2), sup, r*math.sin(remain2)])
                    verts.append([length, sup, -s_sup])
                    #Side 1a
                    verts.append([length, sup, -s_sup])
                    verts.append([length+r+r*math.cos(remain2), sup, r*math.sin(remain2)])
                    verts.append([length+r+r*math.cos(remain2), l, r*math.sin(remain2)])
                    #Side 1b
                    verts.append([length+r+r*math.cos(remain2), l, r*math.sin(remain2)])
                    verts.append([length, l, -s_inf])
                    verts.append([length, sup, -s_sup])
                    #Bottom 
                    verts.append([length+r, l, 0])
                    verts.append([length, l, -s_inf])
                    verts.append([length+r+r*math.cos(remain2), l, r*math.sin(remain2)]) 
                                   
       
        # Add link part between handle and Round Part
        # Top center
        verts.append([length, sup, s_sup])
        verts.append([length+r, sup, 0])
        verts.append([length, sup, -s_sup])
        
        # Bottom  center
        verts.append([length, l, -s_inf])
        verts.append([length+r, l, 0])
        verts.append([length, l, s_inf])

        # Rotate the mesh
        tot = nbvr * 12 + 6 + nbv 
        Tverts = []
        Logger.log('d', "Angle Rotation : {}".format(angle))
        for i in range(0,tot) :           
            xr = (verts[i][0] * math.cos(angle)) - (verts[i][2] * math.sin(angle)) 
            yr = (verts[i][0] * math.sin(angle)) + (verts[i][2] * math.cos(angle))
            zr = verts[i][1]
            Tverts.append([xr, zr, yr])
            
        mesh.setVertices(np.asarray(Tverts, dtype=np.float32))

        indices = []
        for i in range(0, nbv, 4): # All 6 quads (12 triangles)
            indices.append([i, i+2, i+1])
            indices.append([i, i+3, i+2])
            
        # for every angle increment 12 Vertices
        tot = nbvr * 12 + 6 + nbv 
        for i in range(nbv, tot, 3): # 
            indices.append([i, i+1, i+2])
        mesh.setIndices(np.asarray(indices, dtype=np.int32))

        mesh.calculateNormals()
        return mesh
 
    def removeAllSpoonMesh(self):
        if self._all_picked_node:
            for node in self._all_picked_node:
                node_stack = node.callDecoration("getStack")
                if node_stack.getProperty("spoon_mesh", "value"):
                    self._removeSpoonMesh(node)
            self._all_picked_node = []
            self._SMsg = catalog.i18nc("@message", "Remove All") 
            self.propertyChanged.emit()
        else:        
            for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
                if node.callDecoration("isSliceable"):
                    # N_Name=node.getName()
                    # Logger.log('d', 'isSliceable : ' + str(N_Name))
                    node_stack=node.callDecoration("getStack")           
                    if node_stack:        
                        if node_stack.getProperty("spoon_mesh", "value"):
                            # N_Name=node.getName()
                            # Logger.log('d', 'spoon_mesh : ' + str(N_Name)) 
                            self._removeSpoonMesh(node)
 
    # Source code from MeshTools Plugin 
    # Copyright (c) 2020 Aldo Hoeben / fieldOfView
    def _getAllSelectedNodes(self) -> List[SceneNode]:
        selection = Selection.getAllSelectedObjects()[:]
        if selection:
            deep_selection = []  # type: List[SceneNode]
            for selected_node in selection:
                if selected_node.hasChildren():
                    deep_selection = deep_selection + selected_node.getAllChildren()
                if selected_node.getMeshData() != None:
                    deep_selection.append(selected_node)
            if deep_selection:
                return deep_selection

        # Message(catalog.i18nc("@info:status", "Please select one or more models first"))

        return []

    
    def defineAngle(self, Cname : str, act_position: Vector) -> float:
        Angle = 0
        min_lght = 9999999.999
        # Set on the build plate for distance
        calc_position = Vector(act_position.x, 0, act_position.z)
        # Logger.log('d', "Mesh : {}".format(Cname))
        # Logger.log('d', "Position : {}".format(calc_position))

        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            nodes_list = DepthFirstIterator(self._application.getController().getScene().getRoot())
         
        for node in nodes_list:
            if node.callDecoration("isSliceable"):
                # Logger.log('d', "isSliceable : {}".format(node.getName()))
                node_stack=node.callDecoration("getStack")           
                if node_stack:                    
                    if node.getName()==Cname :
                        # Logger.log('d', "Mesh : {}".format(node.getName()))
                        
                        hull_polygon = node.callDecoration("getAdhesionArea")
                        # hull_polygon = node.callDecoration("getConvexHull")
                        # hull_polygon = node.callDecoration("getConvexHullBoundary")
                        # hull_polygon = node.callDecoration("_compute2DConvexHull")
                                   
                        if not hull_polygon or hull_polygon.getPoints is None:
                            Logger.log("w", "Object {} cannot be calculated because it has no convex hull.".format(node.getName()))
                            return 0
                            
                        points=hull_polygon.getPoints()
                        # nb_pt = point[0] / point[1] must be divided by 2
                        # Angle Ref for angle / Y Dir
                        ref = Vector(0, 0, 1)
                        Id=0
                        Start_Id=0
                        End_Id=0
                        for point in points:                               
                            # Logger.log('d', "X : {}".format(point[0]))
                            # Logger.log('d', "Point : {}".format(point))
                            new_position = Vector(point[0], 0, point[1])
                            lg=calc_position-new_position
                            # Logger.log('d', "Lg : {}".format(lg))
                            # lght = lg.length()
                            lght = round(lg.length(),0)

                            if lght<min_lght and lght>0 :
                                min_lght=lght
                                Start_Id=Id
                                Select_position = new_position
                                unit_vector2 = lg.normalized()
                                #Logger.log('d', "unit_vector2 : {}".format(unit_vector2))
                                #LaTan = math.atan(ref.dot(unit_vector2))
                                LeSin = math.asin(ref.dot(unit_vector2))
                                LeCos = math.acos(ref.dot(unit_vector2))
                                
                                if unit_vector2.x>=0 :
                                    Angle = math.pi+LeSin  #angle in radian
                                else :
                                    Angle = -LeSin                                    
                                    
                            if lght==min_lght and lght>0 :
                                if Id > End_Id+1 :
                                    Start_Id=Id
                                    End_Id=Id
                                else :
                                    End_Id=Id
                                    
                            Id+=1
                        
                        # Could be the case with automatic .. rarely in pickpoint   
                        if Start_Id != End_Id :
                            Logger.log('d', "Possibility   : {} / {}".format(Start_Id,End_Id))
                            Id=int(Start_Id+0.5*(End_Id-Start_Id))
                            #Logger.log('d', "Id   : {}".format(Id))
                            new_position = Vector(points[Id][0], 0, points[Id][1])
                            lg=calc_position-new_position                            
                            unit_vector2 = lg.normalized()
                            #Logger.log('d', "unit_vector2 : {}".format(unit_vector2))
                            #LaTan = math.atan(ref.dot(unit_vector2))
                            LeSin = math.asin(ref.dot(unit_vector2))
                            LeCos = math.acos(ref.dot(unit_vector2))
                            
                            if unit_vector2.x>=0 :
                                Angle = math.pi+LeSin  #angle in radian
                            else :
                                Angle = -LeSin
                                    
                        #Logger.log('d', "Pick_position   : {}".format(calc_position))
                        #Logger.log('d', "Close_position  : {}".format(Select_position))
                        #Logger.log('d', "Unit_vector2  : {}".format(unit_vector2))
                        #Logger.log('d', "Angle Sinus     : {}".format(math.degrees(LeSin)))
                        #Logger.log('d', "Angle Cosinus   : {}".format(math.degrees(LeCos)))
                        #Logger.log('d', "Angle Tangente  : {}".format(math.degrees(LaTan)))
                        #Logger.log('d', "Chose Angle     : {}".format(math.degrees(Angle)))
        return Angle
    
    # Automatic creation    
    def addAutoSpoonMesh(self) -> int:
        nb_Tab=0
        act_position = Vector(99999.99,99999.99,99999.99)
        first_pt=Vector

        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            nodes_list = DepthFirstIterator(self._application.getController().getScene().getRoot())
        
        self._op = GroupedOperation()   
        for node in nodes_list:
            if node.callDecoration("isSliceable"):
                Logger.log('d', "isSliceable : {}".format(node.getName()))
                node_stack=node.callDecoration("getStack")           
                if node_stack: 
                    type_infill_mesh = node_stack.getProperty("infill_mesh", "value")
                    type_cutting_mesh = node_stack.getProperty("cutting_mesh", "value")
                    type_support_mesh = node_stack.getProperty("support_mesh", "value")
                    type_spoon_mesh = node_stack.getProperty("spoon_mesh", "value")
                    type_anti_overhang_mesh = node_stack.getProperty("anti_overhang_mesh", "value") 
                    
                    if not type_infill_mesh and not type_support_mesh and not type_anti_overhang_mesh :
                    # and Selection.isSelected(node)
                        Logger.log('d', "Mesh : {}".format(node.getName()))
                        
                        # hull_polygon = node.callDecoration("getAdhesionArea")
                        # hull_polygon = node.callDecoration("getConvexHull")
                        # hull_polygon = node.callDecoration("getConvexHullBoundary")
                        hull_polygon = node.callDecoration("_compute2DConvexHull")
                                   
                        if not hull_polygon or hull_polygon.getPoints is None:
                            Logger.log("w", "Object {} cannot be calculated because it has no convex hull.".format(node.getName()))
                            continue
                            
                        points=hull_polygon.getPoints()
                        # nb_pt = point[0] / point[1] must be divided by 2
                        nb_pt=points.size*0.5
                        # Logger.log('d', "Size pt : {}".format(nb_pt))
                        
                        for point in points:
                            nb_Tab+=1
                            # Logger.log('d', "Nb_Tab : {}".format(nb_Tab))
                            if nb_Tab == 1:
                                first_pt = Vector(point[0], 0, point[1])
                                # Logger.log('d', "First X : {}".format(point[0]))
                                # Logger.log('d', "First Y : {}".format(point[1]))
                                
                            # Logger.log('d', "X : {}".format(point[0]))
                            # Logger.log('d', "Y : {}".format(point[1]))
                            new_position = Vector(point[0], 0, point[1])
                            lg=act_position-new_position
                            lght = lg.length()
                            # Logger.log('d', "Length : {}".format(lght))
                            # Add a tab if the distance between 2 tabs are more than a Tab Radius
                            # We have to tune this parameter or algorythm in the futur
                            if nb_Tab == nb_pt:
                                lgfl=(first_pt-new_position).length()
                                 
                                # Logger.log('d', "Length First Last : {}".format(lgfl))
                                if lght >= (self._UseSize*0.5) and lgfl >= (self._UseSize*0.5) :
                                    self._createSpoonMesh(node, new_position)
                                    act_position = new_position                               
                            else:
                                if lght >= (self._UseSize*0.5) :
                                    self._createSpoonMesh(node, new_position)
                                    act_position = new_position
                                  
        self._op.push() 
        return nb_Tab

    def getSMsg(self) -> bool:
        """ 
            return: golabl _SMsg  as text paramater.
        """ 
        return self._SMsg
    
    def setSMsg(self, SMsg: str) -> None:
        """
        param SType: SMsg as text paramater.
        """
        self._SMsg = SMsg
        
    def getSSize(self) -> float:
        """ 
            return: golabl _UseSize  in mm.
        """           
        return self._UseSize
  
    def setSSize(self, SSize: str) -> None:
        """
        param SSize: Size in mm.
        """
 
        try:
            s_value = float(SSize)
        except ValueError:
            return

        if s_value <= 0:
            return      
        #Logger.log('d', 's_value : ' + str(s_value))        
        self._UseSize = s_value
        self._preferences.setValue("spoon_anti_warping/s_size", s_value)
 
    def getNLayer(self) -> int:
        """ 
            return: golabl _Nb_Layer
        """           
        return self._Nb_Layer
  
    def setNLayer(self, NLayer: str) -> None:
        """
        param NLayer: NLayer as integer >1
        """
 
        try:
            i_value = int(NLayer)
            
        except ValueError:
            return
 
        if i_value < 1:
            return
        
        #Logger.log('d', 'i_value : ' + str(i_value))        
        self._Nb_Layer = i_value
        self._preferences.setValue("spoon_anti_warping/nb_layer", i_value)
        
    def getSLength(self) -> float:
        """ 
            return: golabl _UseLength  in mm.
        """           
        return self._UseLength
  
    def setSLength(self, SLength: str) -> None:
        """
        param SLength: SLength in mm.
        """
 
        try:
            s_value = float(SLength)
        except ValueError:
            return
        
        #Logger.log('d', 's_value : ' + str(s_value))        
        self._UseLength = s_value
        self._preferences.setValue("spoon_anti_warping/s_length", s_value) 

    def getSWidth(self) -> float:
        """ 
            return: golabl _UseWidth  in mm.
        """           
        return self._UseWidth
  
    def setSWidth(self, SWidth: str) -> None:
        """
        param SWidth : SWidth in mm.
        """
 
        try:
            s_value = float(SWidth)
        except ValueError:
            return
        
        #Logger.log('d', 's_value : ' + str(s_value))     
        self._UseWidth = s_value
        self._preferences.setValue("spoon_anti_warping/s_width", s_value) 
