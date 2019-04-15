# OctoPrint-Print-Queue (Modified)

Attention this is a modified version of https://github.com/michaelnew/Octoprint-Print-Queue. It is for adding a Universal Robot UR3 to the setup to clean the plate after each print.

This plugin proves a way to print one object after another. After printing an object it will run a gcode script (that you provide) to clear the print bed, and then will start printing the next object in the queue.

This plugin only works if you have some way of automaticaly clearing your print bed. If the print does not successfully clear before starting the next one, all manner of Bad Things are likely to happen.