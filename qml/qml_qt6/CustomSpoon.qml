//-----------------------------------------------------------------------------
// Copyright (c) 2023 5@xes
// 
// proterties values
//   "SSize"       : Tab Size in mm
//   "SLength"     : Length set for Tab in mm
//   "SWidth"      : Width set for Tab in mm
//   "SCapsule"    : Define as capsule
//   "NLayer"      : Number of layer
//   "ISpeed"      : Initial Speed in mm/s
//   "DirectShape" : Direct shape
//   "SMsg"        : Text for the Remove All Button
//
//-----------------------------------------------------------------------------

import QtQuick 6.0
import QtQuick.Controls 6.0

import UM 1.6 as UM
import Cura 1.0 as Cura

Item
{
    id: base
    width: childrenRect.width
    height: childrenRect.height
    UM.I18nCatalog { id: catalog; name: "spoonantiwarping"}
	
	property int localwidth:70


    Grid
    {
        id: textfields

        anchors.leftMargin: UM.Theme.getSize("default_margin").width
        anchors.top: parent.top

        columns: 2
        flow: Grid.LeftToRight
        spacing: Math.round(UM.Theme.getSize("default_margin").width / 2)

        Label
        {
            height: UM.Theme.getSize("setting_control").height
            text: catalog.i18nc("@label", "Diameter")
            font: UM.Theme.getFont("default")
            color: UM.Theme.getColor("text")
            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
            width: Math.ceil(contentWidth) //Make sure that the grid cells have an integer width.
        }

		UM.TextFieldWithUnit
        {
            id: sizeTextField
            width: localwidth
            height: UM.Theme.getSize("setting_control").height
            unit: "mm"
            text: UM.ActiveTool.properties.getValue("SSize")
            validator: DoubleValidator
            {
                decimals: 1
                bottom: 0.1
                locale: "en_US"
            }

            onEditingFinished:
            {
                var modified_text = text.replace(",", ".") // User convenience. We use dots for decimal values
                UM.ActiveTool.setProperty("SSize", modified_text)
            }
        }
		
        Label
        {
            height: UM.Theme.getSize("setting_control").height
            text: catalog.i18nc("@label", "Spoon Handle Length")
            font: UM.Theme.getFont("default")
            color: UM.Theme.getColor("text")
            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
            width: Math.ceil(contentWidth) //Make sure that the grid cells have an integer width.
        }

		UM.TextFieldWithUnit
        {
            id: lengthTextField
            width: localwidth
            height: UM.Theme.getSize("setting_control").height
            unit: "mm"
            text: UM.ActiveTool.properties.getValue("SLength")
            validator: DoubleValidator
            {
                decimals: 2
				bottom: 0
                locale: "en_US"
            }

            onEditingFinished:
            {
                var modified_text = text.replace(",", ".") // User convenience. We use dots for decimal values
                UM.ActiveTool.setProperty("SLength", modified_text)
            }
        }

        Label
        {
            height: UM.Theme.getSize("setting_control").height
            text: catalog.i18nc("@label", "Spoon Handle Width")
            font: UM.Theme.getFont("default")
            color: UM.Theme.getColor("text")
            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
            width: Math.ceil(contentWidth) //Make sure that the grid cells have an integer width.
        }

		UM.TextFieldWithUnit
        {
            id: widthTextField
            width: localwidth
            height: UM.Theme.getSize("setting_control").height
            unit: "mm"
            text: UM.ActiveTool.properties.getValue("SWidth")
            validator: DoubleValidator
            {
                decimals: 2
				bottom: 0
				top: UM.ActiveTool.properties.getValue("SSize")
                locale: "en_US"
            }

            onEditingFinished:
            {
                var modified_text = text.replace(",", ".") // User convenience. We use dots for decimal values
                UM.ActiveTool.setProperty("SWidth", modified_text)
            }
        }		
		
        Label
        {
            height: UM.Theme.getSize("setting_control").height
            text: catalog.i18nc("@label", "Number of layers")
            font: UM.Theme.getFont("default")
            color: UM.Theme.getColor("text")
            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
            width: Math.ceil(contentWidth) //Make sure that the grid cells have an integer width.
        }

		UM.TextFieldWithUnit
        {
            id: numberlayerTextField
            width: localwidth
            height: UM.Theme.getSize("setting_control").height
            text: UM.ActiveTool.properties.getValue("NLayer")
            validator: IntValidator
            {
				bottom: 1
				top: 100
            }

            onEditingFinished:
            {
                UM.ActiveTool.setProperty("NLayer", text)
            }
        }	
		
	    Label
        {
            height: UM.Theme.getSize("setting_control").height
            text: catalog.i18nc("@label", "Initial Layer Speed")
            font: UM.Theme.getFont("default")
            color: UM.Theme.getColor("text")
            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
            width: Math.ceil(contentWidth) //Make sure that the grid cells have an integer width.
        }

		UM.TextFieldWithUnit
        {
            id: initialTextField
            width: localwidth
            height: UM.Theme.getSize("setting_control").height
			unit: "mm/s"
            text: UM.ActiveTool.properties.getValue("ISpeed")
            validator: DoubleValidator
            {
                decimals: 1
				bottom: 0
                locale: "en_US"
            }
            onEditingFinished:
            {
			    var modified_text = text.replace(",", ".") // User convenience. We use dots for decimal values
                UM.ActiveTool.setProperty("ISpeed", modified_text)
            }
        }
		
		UM.CheckBox {
			text: catalog.i18nc("@option:check","Direct shape")
			checked: UM.ActiveTool.properties.getValue("DirectShape")
			onClicked: {
				UM.ActiveTool.setProperty("DirectShape", checked)
			}
		}
	}

	Rectangle {
        id: topRect
        anchors.top: textfields.bottom 
		//color: UM.Theme.getColor("toolbar_background")
		color: "#00000000"
		width: UM.Theme.getSize("setting_control").width * 1.3
		height: UM.Theme.getSize("setting_control").height 
        anchors.left: parent.left
		anchors.topMargin: UM.Theme.getSize("default_margin").height
    }
	
	Cura.SecondaryButton
	{
		id: removeAllButton
		anchors.centerIn: topRect
		spacing: UM.Theme.getSize("default_margin").height
		width: UM.Theme.getSize("setting_control").width
		height: UM.Theme.getSize("setting_control").height	
		text: catalog.i18nc("@message", UM.ActiveTool.properties.getValue("SMsg"))
		onClicked: UM.ActiveTool.triggerAction("removeAllSpoonMesh")
	}
	
	Rectangle {
        id: bottomRect
        anchors.top: topRect.bottom
		//color: UM.Theme.getColor("toolbar_background")
		color: "#00000000"
		width: UM.Theme.getSize("setting_control").width * 1.3
		height: UM.Theme.getSize("setting_control").height 
        anchors.left: parent.left
		anchors.topMargin: UM.Theme.getSize("default_margin").height
    }
	
	Cura.SecondaryButton
	{
		id: addAllButton
		anchors.centerIn: bottomRect
		spacing: UM.Theme.getSize("default_margin").height
		width: UM.Theme.getSize("setting_control").width
		height: UM.Theme.getSize("setting_control").height	
		text: catalog.i18nc("@label", "Automatic Addition")
		onClicked: UM.ActiveTool.triggerAction("addAutoSpoonMesh")
	}
	

}
