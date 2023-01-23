# Spoon Anti-Warping

Plugin Cura Spoon Anti-Warping.


![Spoon Anti-Warping](https://github.com/5axes/SpoonAntiWarping/blob/main/images/SpoonAntiWarping.png)

The Spoon Anti-warping plugin is a tool designed to prevent warping of sharp edges in 3D printing. Warping is a common issue that occurs when a 3D printed object is cooled too quickly, causing the edges to curl or bend. The Spoon Anti-warping plugin addresses this problem by adding tabs to the design of the object.

Tabs are small, flat extensions that are added to the edges of the object. These tabs act as anchors, holding the edges in place as the object cools and preventing them from warping. The size and number of tabs can be adjusted to suit the specific needs of the object being printed.


The Spoon Anti-warping plugin offers two methods for adding tabs to a 3D printed object: manual and automatic.

![Plugin Cura Spoon Anti-Warping. options](https://github.com/5axes/SpoonAntiWarping/blob/main/images/options.png)


The manual method allows users to manually select the position of the tabs on the object. This method is useful for adding tabs to specific areas that are prone to warping, such as sharp edges or thin sections. To use the manual method, the user simply selects the positioin where they want to add the tabs and clicks to create them. This allows for precise control over the number and placement of tabs, which can be important in some cases.

The automatic method, on the other hand, uses an algorithm to automatically generate tabs in the convex_hull border of the part. This method is useful for those who want to quickly add tabs to an entire object without having to manually select each location. 


### Notes

In order for the Spoon Anti-warping plugin to work correctly in the Cura slicing software, the adherence option must be enabled. This option creates internaly in Cura an adherence border.

![Cura Adhesion option](https://github.com/5axes/SpoonAntiWarping/blob/main/images/adhesion.png)

Even if the user does not want to use the raft for the final print, it is necessary to have it enabled while using the Spoon Anti-warping plugin. The plugin uses the these border to calculate the tab orientation. Once the tabs creation is complete, you can remove this option if you don't want anay adherence option creation in the final print.


### YouTube video

[![Spoon Anti-Warping](http://img.youtube.com/vi/K2niowptW7M/0.jpg)](https://www.youtube.com/watch?v=K2niowptW7M)
