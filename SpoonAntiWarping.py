#--------------------------------------------------------------------------------------------------------------------------------------
# Copyright (c) 2023 5@xes
#--------------------------------------------------------------------------------------------------------------------------------------
# Based on the TabPlus plugin by 5@xes, and licensed under LGPLv3 or higher.
#
#  https://github.com/5axes/TabPlus
#
# All modification 5@xes
# First release  22-01-2023  First proof of concept
# Second release  23-01-2023  Limit the number of Tab with Circular element
#--------------------------------------------------------------------------------------------------------------------------------------
# V0.0.3 24-01-2023 Test if the adherence is set, if not set to Skirt   / Test the value for the length and the width of the handle
#                                                                           Can be equal to Zero
# V0.0.4 25-01-2023 Change some label in the i18n files for automatic pot file generation on github
# V0.0.5 03-02-2023 Reset data for delete tabs on a new fileload
# V0.0.6 07-02-2023 Change position of Angle calculation
# V0.0.7 09-02-2023 Clean the code and Online on Ultimaker Market
# V1.0.0 12-02-2023 Change to 1.0.0 after online Ultimaker Market
# V1.0.1 12-02-2023 Add option for Initial Layer Speed for the spoon ( If Speed >0 )
# V1.0.2 15-02-2023 correct bug
# V1.1.0 20-02-2023 Define as direct shape
#--------------------------------------------------------------------------------------------------------------------------------------

VERSION_QT5 = False
try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import QApplication
    VERSION_QT5 = True


import os.path 
import math
import numpy as np

from typing import Optional, List
from collections import OrderedDict

from cura.CuraApplication import CuraApplication
from cura.PickingPass import PickingPass
from cura.CuraVersion import CuraVersion  # type: ignore
from cura.Operations.SetParentOperation import SetParentOperation
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode

from UM.Resources import Resources
from UM.Logger import Logger
from UM.Message import Message
from UM.Math.Vector import Vector
from UM.Tool import Tool
from UM.Event import Event, MouseEvent
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Settings.SettingInstance import SettingInstance
from UM.Settings.SettingDefinition import SettingDefinition
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Settings.ContainerRegistry import ContainerRegistry
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Scene.Selection import Selection
from UM.Scene.SceneNode import SceneNode
from UM.Scene.Iterator.DepthFirstIterator import DepthFirstIterator
from UM.Tool import Tool
from UM.Version import Version
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
        self._UseLength = 2.0
        self._UseWidth = 2.0
        self._InitialLayerSpeed = 0.0
        self._Nb_Layer = 1
        self._Mesg = False # To avoid message 
        self._direct_shape = False
        self._SMsg = catalog.i18nc("@label", "Remove All") 

        # Shortcut
        if not VERSION_QT5:
            self._shortcut_key = Qt.Key.Key_K
        else:
            self._shortcut_key = Qt.Key_K
            
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
        
        self.setExposedProperties("SSize", "SLength", "SWidth", "NLayer", "ISpeed", "DirectShape", "SMsg" )
        
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
 
        self._preferences.addPreference("spoon_anti_warping/s_length", 2)
        # convert as float to avoid further issue
        self._UseLength = float(self._preferences.getValue("spoon_anti_warping/s_length"))

        self._preferences.addPreference("spoon_anti_warping/s_width", 2)
        # convert as float to avoid further issue
        self._UseWidth = float(self._preferences.getValue("spoon_anti_warping/s_width"))

        self._preferences.addPreference("spoon_anti_warping/s_initial_layer_speed", 0)
        self._InitialLayerSpeed = float(self._preferences.getValue("spoon_anti_warping/s_initial_layer_speed"))
        
        self._preferences.addPreference("spoon_anti_warping/nb_layer", 1)
        # convert as float to avoid further issue
        self._Nb_Layer = int(self._preferences.getValue("spoon_anti_warping/nb_layer"))       

        self._preferences.addPreference("spoon_anti_warping/direct_shape", False)
        # convert as bool to avoid further issue
        self._direct_shape = bool(self._preferences.getValue("spoon_anti_warping/direct_shape")) 

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
        self._application.fileCompleted.connect(self._onFileCompleted)
        # Logger.log('d', "Info CuraVersion --> " + str(CuraVersion))

    def _onFileCompleted(self) -> None:
        # Reset Stock Data  
        self._all_picked_node = []
        self._SMsg = catalog.i18nc("@label", "Remove All") 
            
    def event(self, event):
        super().event(event)
        modifiers = QApplication.keyboardModifiers()
        if not VERSION_QT5:
            ctrl_is_active = modifiers & Qt.KeyboardModifier.ControlModifier
        else:
            ctrl_is_active = modifiers & Qt.ControlModifier

        if event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons and self._controller.getToolsEnabled():
            if ctrl_is_active:
                self._controller.setActiveTool("RotateTool")
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
                # if it's a spoon_mesh -> remove it
                if node_stack.getProperty("spoon_mesh", "value"):
                    self._removeSpoonMesh(picked_node)
                    return
                
                elif node_stack.getProperty("anti_overhang_mesh", "value") or node_stack.getProperty("infill_mesh", "value") or node_stack.getProperty("support_mesh", "value"):
                    # Only "normal" meshes can have spoon_mesh added to them
                    # Try to add also to support but as support got a X/Y distance/ part it's useless
                    return

            # Create a pass for picking a world-space location from the mouse location
            active_camera = self._controller.getScene().getActiveCamera()
            picking_pass = PickingPass(active_camera.getViewportWidth(), active_camera.getViewportHeight())
            picking_pass.render()

            picked_position = picking_pass.getPickedPosition(event.x, event.y)

            # Logger.log('d', "X : {}".format(picked_position.x))
            # Logger.log('d', "Y : {}".format(picked_position.y))
            # Logger.log('d', "Name : {}".format(node_stack.getName()))
                            
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
        
        # local_transformation = parent.getLocalTransformation()
        # Logger.log('d', "Parent local_transformation --> " + str(local_transformation))
        
        node.setName("SpoonTab")           
        node.setSelectable(True)
        
        # long=Support Height
        _long=position.y

        # get layer_height_0 used to define pastille height
        _id_ex=0
        
        # This function can be triggered in the middle of a machine change, so do not proceed if the machine change has not done yet.
        global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        #extruder = global_container_stack.extruderList[int(_id_ex)] 
        extruder_stack = CuraApplication.getInstance().getExtruderManager().getActiveExtruderStacks()[0]     
        #self._Extruder_count=global_container_stack.getProperty("machine_extruder_count", "value") 
        
        _layer_h_i = extruder_stack.getProperty("layer_height_0", "value")
        _layer_height = extruder_stack.getProperty("layer_height", "value")
        _layer_h = (_layer_h_i * 1.2) + (_layer_height * (self._Nb_Layer -1) )

        key = "adhesion_type"
        adhesion=global_container_stack.getProperty(key, "value") 
           
        if adhesion ==  'none' :
            if not self._Mesg :
                definition_key=key + " label"
                untranslated_label=extruder_stack.getProperty(key,"label")
                translated_label=i18n_catalog.i18nc(definition_key, untranslated_label) 
                Format_String = catalog.i18nc("@info:label", "Info modification current profile '") + translated_label  + catalog.i18nc("@info:label", "' parameter\nNew value : ") + catalog.i18nc("@info:label", "Skirt")                
                Message(text = Format_String, title = catalog.i18nc("@info:title", "Warning ! Spoon Anti-Warping")).show()
                self._Mesg = True
            # Define temporary adhesion_type=skirt to force boundary calculation ?
            global_container_stack.setProperty(key, "value", 'skirt')
            Logger.log('d', "Info adhesion_type --> " + str(adhesion)) 

        _angle = self.defineAngle(EName,position)
        # Logger.log('d', "Info createSpoonMesh Angle --> " + str(_angle))
                
        # Spoon creation Diameter , Length, Width, Increment angle 10°, length, layer_height_0*1.2
        mesh = self._createSpoon(self._UseSize,self._UseLength,self._UseWidth, 10,_long,_layer_h , self._direct_shape, _angle)
        
        # new_transformation = Matrix()
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
        
        # speed_layer_0
        if self._InitialLayerSpeed > 0 :
            definition = stack.getSettingDefinition("speed_layer_0")
            new_instance = SettingInstance(definition, settings)
            new_instance.setProperty("value", self._InitialLayerSpeed) # initial layer speed
            new_instance.resetState()  # Ensure that the state is not seen as a user state.
            settings.addInstance(new_instance)   
        
        definition = stack.getSettingDefinition("infill_mesh_order")
        new_instance = SettingInstance(definition, settings)
        new_instance.setProperty("value", 49) #50 "maximum_value_warning": "50"
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
        # First add node to the scene at the correct position/scale, before parenting, so the Spoon mesh does not get scaled with the parent
        self._op.addOperation(AddSceneNodeOperation(node, self._controller.getScene().getRoot())) # This one will set the model with the right transformation
        self._op.addOperation(SetParentOperation(node, parent)) # This one will link the tab with the parent ( Scale)
        
        node.setPosition(position, CuraSceneNode.TransformSpace.World)  # Set the World Transformmation
        
        self._all_picked_node.append(node)
        self._SMsg = catalog.i18nc("@label", "Remove Last") 
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

    def _tangential_point_on_circle(self,center, radius, point_fixe):
        # Calculation of the distance between point_fix and (center[0], center[1])
        d = math.sqrt((center[0] - point_fixe[0])**2 + (center[1] - point_fixe[1])**2)

        # Search for the points of tangency of the line with the circle
        tangency_points = []

        # If point_fix is on the circle, there is only one point of tangency
        if d == radius:
            tangency_points.append(point_fixe[0])
            tangency_points.append(point_fixe[1])
           
        else:
            p = math.sqrt( d**2-radius**2)
            # Calculation of the angle between the line and the radius of the circle passing through the point of tangency
            theta = math.asin(radius / d)
            # Calculation of the angle of the line
            alpha = math.atan2(center[1] - point_fixe[1] , center[0] - point_fixe[0] )
            # Calculation of the angles of the two rays passing through the points of tangency
            beta1 = alpha + theta
            beta2 = alpha - theta
            # Calculation of the coordinates of the tangency points
            tx1 = center[0] - radius* math.sin(beta1)
            ty1 = center[1] + radius* math.cos(beta1)
            tangency_points.append(tx1)
            tangency_points.append(ty1)
        return tangency_points
        
    # SPOON creation
    def _createSpoon(self, size , length , width , nb , lg, He ,direct_shape ,angle):   
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
        
        if direct_shape :
            p = [-s_sup,s_sup]
            c = [(r+length),0]
            result = self._tangential_point_on_circle(c,r,p)
            Logger.log('d', "Point tangence : {}".format(result))
            nbv=20 
            verts = [ # 5 faces with 4 corners each
                [-s_inf, l,  s_inf], [-s_sup,  sup,  s_sup], [ result[0],  sup,  result[1]], [ result[0], l,  result[1]],
                [-s_sup,  sup, -s_sup], [-s_inf, l, -s_inf], [ result[0], l, -result[1]], [ result[0],  sup, -result[1]],
                [ result[0], l, -result[1]], [-s_inf, l, -s_inf], [-s_inf, l,  s_inf], [ result[0], l,  result[1]],
                [-s_sup,  sup, -s_sup], [ result[0],  sup, -result[1]], [ result[0],  sup,  result[1]], [-s_sup,  sup,  s_sup],
                [-s_inf, l,  s_inf], [-s_inf, l, -s_inf], [-s_sup,  sup, -s_sup], [-s_sup,  sup,  s_sup]
            ]
            max_val=result[1]
            max_l=result[0]
        else:
            nbv=20 
            verts = [ # 5 faces with 4 corners each
                [-s_inf, l,  s_inf], [-s_sup,  sup,  s_sup], [ length,  sup,  s_sup], [ length, l,  s_inf],
                [-s_sup,  sup, -s_sup], [-s_inf, l, -s_inf], [ length, l, -s_inf], [ length,  sup, -s_sup],
                [ length, l, -s_inf], [-s_inf, l, -s_inf], [-s_inf, l,  s_inf], [ length, l,  s_inf],
                [-s_sup,  sup, -s_sup], [ length,  sup, -s_sup], [ length,  sup,  s_sup], [-s_sup,  sup,  s_sup],
                [-s_inf, l,  s_inf], [-s_inf, l, -s_inf], [-s_sup,  sup, -s_sup], [-s_sup,  sup,  s_sup]
            ] 
            max_val=s_sup
            max_l=length
        
        # Add Round Part of the Spoon
        nbvr = 0
        remain1 = 0
        remain2 = 0

        for i in range(0, rng):
            if (r*math.cos((i+1)*ang)) >= 0 or (abs(r*math.sin((i+1)*ang)) > max_val and abs(r*math.sin(i*ang)) > max_val)  :
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
                    
                    if direct_shape :
                        lg = max_l
                    else:
                        lg = length
                        
                    nbvr += 1
                    # Top
                    verts.append([length+r, sup, 0])
                    verts.append([lg, sup, max_val])
                    verts.append([length+r+r*math.cos(remain1), sup, r*math.sin(remain1)])
                    #Side 1a
                    verts.append([length+r+r*math.cos(remain1), sup, r*math.sin(remain1)])
                    verts.append([lg, sup, max_val])
                    verts.append([lg, l, max_val])
                    #Side 1b
                    verts.append([lg, l, max_val])
                    verts.append([length+r+r*math.cos(remain1), l, r*math.sin(remain1)])
                    verts.append([length+r+r*math.cos(remain1), sup, r*math.sin(remain1)])
                    #Bottom 
                    verts.append([length+r, l, 0])
                    verts.append([length+r+r*math.cos(remain1), l, r*math.sin(remain1)])
                    verts.append([lg, l, max_val])  
                    
                    nbvr += 1 
                    # Top
                    verts.append([length+r, sup, 0])
                    verts.append([length+r+r*math.cos(remain2), sup, r*math.sin(remain2)])
                    verts.append([lg, sup, -max_val])
                    #Side 1a
                    verts.append([lg, sup, -max_val])
                    verts.append([length+r+r*math.cos(remain2), sup, r*math.sin(remain2)])
                    verts.append([length+r+r*math.cos(remain2), l, r*math.sin(remain2)])
                    #Side 1b
                    verts.append([length+r+r*math.cos(remain2), l, r*math.sin(remain2)])
                    verts.append([lg, l, -max_val])
                    verts.append([lg, sup, -max_val])
                    #Bottom 
                    verts.append([length+r, l, 0])
                    verts.append([lg, l, -max_val])
                    verts.append([length+r+r*math.cos(remain2), l, r*math.sin(remain2)]) 

       
        # Add link part between handle and Round Part
        # Top center
        verts.append([max_l, sup, max_val])
        verts.append([length+r, sup, 0])
        verts.append([max_l, sup, -max_val])
        
        # Bottom  center
        verts.append([max_l, l, -max_val])
        verts.append([length+r, l, 0])
        verts.append([max_l, l, max_val])

        # Rotate the mesh
        tot = nbvr * 12 + 6 + nbv 
        Tverts = []
        # Logger.log('d', "Angle Rotation : {}".format(angle))
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
            self._SMsg = catalog.i18nc("@label", "Remove All") 
            self.propertyChanged.emit()
        else:        
            for node in DepthFirstIterator(self._application.getController().getScene().getRoot()):
                if node.callDecoration("isSliceable"):
                    node_stack=node.callDecoration("getStack")           
                    if node_stack:        
                        if node_stack.getProperty("spoon_mesh", "value"):
                            # Logger.log('d', "spoon_mesh : {}".format(node.getName())) 
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
                            # Logger.log('d', "Point : {}".format(point))
                            new_position = Vector(point[0], 0, point[1])
                            lg=calc_position-new_position
                            # lght = lg.length()
                            lght = round(lg.length(),0)

                            if lght<min_lght and lght>0 :
                                min_lght=lght
                                Start_Id=Id
                                Select_position = new_position
                                unit_vector2 = lg.normalized()
                                LeSin = math.asin(ref.dot(unit_vector2))
                                #LeCos = math.acos(ref.dot(unit_vector2))
                                
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
                            Id=int(Start_Id+0.5*(End_Id-Start_Id))
                            new_position = Vector(points[Id][0], 0, points[Id][1])
                            lg=calc_position-new_position                            
                            unit_vector2 = lg.normalized()
                            LeSin = math.asin(ref.dot(unit_vector2))
                            # LeCos = math.acos(ref.dot(unit_vector2))
                            
                            if unit_vector2.x>=0 :
                                Angle = math.pi+LeSin  #angle in radian
                            else :
                                Angle = -LeSin
                                    
                        # Logger.log('d', "Pick_position   : {}".format(calc_position))
                        # Logger.log('d', "Close_position  : {}".format(Select_position))
                        # Logger.log('d', "Unit_vector2    : {}".format(unit_vector2))
                        # Logger.log('d', "Angle Sinus     : {}".format(math.degrees(LeSin)))
                        # Logger.log('d', "Angle Cosinus   : {}".format(math.degrees(LeCos)))
                        # Logger.log('d', "Chose Angle     : {}".format(math.degrees(Angle)))
        return Angle
    
    # Automatic creation    
    def addAutoSpoonMesh(self) -> int:
        nb_Tab=0
        act_position = Vector(99999.99,99999.99,99999.99)
        first_pt=Vector

        nodes_list = self._getAllSelectedNodes()
        if not nodes_list:
            nodes_list = DepthFirstIterator(self._application.getController().getScene().getRoot())

        if self._all_picked_node:
            self._all_picked_node = []
            self._SMsg = catalog.i18nc("@label", "Remove All") 
        
        self._op = GroupedOperation()   
        for node in nodes_list:
            if node.callDecoration("isSliceable"):
                # Logger.log('d', "isSliceable : {}".format(node.getName()))
                node_stack=node.callDecoration("getStack")           
                if node_stack: 
                    type_infill_mesh = node_stack.getProperty("infill_mesh", "value")
                    type_cutting_mesh = node_stack.getProperty("cutting_mesh", "value")
                    type_support_mesh = node_stack.getProperty("support_mesh", "value")
                    type_spoon_mesh = node_stack.getProperty("spoon_mesh", "value")
                    type_anti_overhang_mesh = node_stack.getProperty("anti_overhang_mesh", "value") 
                    
                    if not type_infill_mesh and not type_support_mesh and not type_anti_overhang_mesh :
                    # and Selection.isSelected(node)
                        # Logger.log('d', "Mesh : {}".format(node.getName()))
                        
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
                            lght = round(lg.length(),0)
                            # Logger.log('d', "Length : {}".format(lght))
                            # Add a tab if the distance between 2 tabs are more than a Tab Radius
                            # We have to tune this parameter or algorythm in the futur
                            if nb_Tab == nb_pt:
                                lgfl=(first_pt-new_position).length()
                                 
                                # Logger.log('d', "Length First Last : {}".format(lgfl))
                                if lght >= (self._UseSize*0.8) and lgfl >= (self._UseSize*0.8) :
                                    self._createSpoonMesh(node, new_position)
                                    act_position = new_position                               
                            else:
                                if lght >= (self._UseSize*0.8) :
                                    self._createSpoonMesh(node, new_position)
                                    act_position = new_position
                                  
        self._op.push() 
        return nb_Tab

    def getSMsg(self) -> bool:
        """ 
            return: global _SMsg  as text paramater.
        """ 
        return self._SMsg
    
    def setSMsg(self, SMsg: str) -> None:
        """
        param SType: SMsg as text paramater.
        """
        self._SMsg = SMsg
        
    def getSSize(self) -> float:
        """ 
            return: global _UseSize  in mm.
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
        
    def getSLength(self) -> float:
        """ 
            return: global _UseLength  in mm.
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

        if s_value < 0:
            return         
        #Logger.log('d', 's_value : ' + str(s_value))        
        self._UseLength = s_value
        self._preferences.setValue("spoon_anti_warping/s_length", s_value) 

    def getSWidth(self) -> float:
        """ 
            return: global _UseWidth  in mm.
        """           
        return self._UseWidth
  
    def setSWidth(self, SWidth: str) -> None:
        """
        param SWidth : Width in mm.
        """
 
        try:
            s_value = float(SWidth)
        except ValueError:
            return

        if s_value < 0:
            return         
        #Logger.log('d', 's_value : ' + str(s_value))     
        self._UseWidth = s_value
        self._preferences.setValue("spoon_anti_warping/s_width", s_value) 

    def getISpeed(self) -> float:
        """ 
            return: global _InitialLayerSpeed  in mm/s.
        """           
        return self._InitialLayerSpeed
  
    def setISpeed(self, ISpeed: str) -> None:
        """
        param ISpeed : ISpeed in mm/s.
        """
 
        try:
            s_value = float(ISpeed)
        except ValueError:
            return

        if s_value < 0: 
            return         
        # Logger.log('d', 'ISpeed : ' + str(s_value))     
        self._InitialLayerSpeed = s_value
        self._preferences.setValue("spoon_anti_warping/s_initial_layer_speed", s_value) 
        
    def getNLayer(self) -> int:
        """ 
            return: global _Nb_Layer
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

    def getDirectShape(self )-> bool:
        return self._direct_shape

    def setDirectShape(self, value: bool) -> None:
        # Logger.log("w", "setDirectShape {}".format(value))
        self._direct_shape = value
        self.propertyChanged.emit()
        self._preferences.setValue("spoon_anti_warping/direct_shape", self._direct_shape)
