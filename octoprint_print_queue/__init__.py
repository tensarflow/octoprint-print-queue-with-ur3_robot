# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from pprint import pprint
from octoprint.server import printer, NO_CONTENT
import flask, json
import os
import socket
import time
import math as m
import sys

class PrintQueuePlugin(octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.EventHandlerPlugin):

    printqueue = []
    selected_file = ""
    uploads_dir = "C:\\Users\\teozk\\AppData\\Roaming\\OctoPrint\\uploads\\"
# StartupPlugin
    def on_after_startup(self):
        self._print_queue_file_path = os.path.join(self.get_plugin_data_folder(), "print_queue.yaml")
        self._configuration_dict = None
        self._getConfigurationFile()


# BluePrintPlugin (api requests)
    @octoprint.plugin.BlueprintPlugin.route("/scriptget", methods=["GET"])
    def getMaterialsData(self):
        return flask.jsonify(self._getConfigurationFile())

    @octoprint.plugin.BlueprintPlugin.route("/scriptset", methods=["POST"])
    def setMaterialsData(self):
        config = self._getConfigurationFile()
        config["bed_clear_script"] = flask.request.values["bed_clear_script"];
        self._writeConfigurationFile(config)
        return flask.make_response("POST successful", 200)

    @octoprint.plugin.BlueprintPlugin.route("/addselectedfile", methods=["GET"])
    def addSelectedFile(self):
        self._logger.info("PQ: adding selected file: " + self.selected_file)
        self._printer.unselect_file()
        f = self.selected_file
        self.selected_file = ""
        return flask.jsonify(filename=f)

    @octoprint.plugin.BlueprintPlugin.route("/clearselectedfile", methods=["POST"])
    def clearSelectedFile(self):
        self._logger.info("PQ: clearing selected file")
        self._printer.unselect_file()
        self.selected_file = ""
        return flask.make_response("POST successful", 200)

    @octoprint.plugin.BlueprintPlugin.route("/printcontinuously", methods=["POST"])
    def printContinuously(self):
        self.printqueue = []
        for v in flask.request.form:
            j = json.loads(v)
            for p in j:
                self.printqueue += [p]

        f = self.uploads_dir + self.printqueue[0]
        self._logger.info("PQ: attempting to select and print file: " + f)
        self._printer.select_file(f, False, True)
        self.printqueue.pop(0)
        return flask.make_response("POST successful", 200)

# TemplatePlugin
    def get_template_vars(self):
        return dict(
            bed_temp=self._settings.get(["bed_temp"]),
            print_temp=self._settings.get(["print_temp"]))

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False),
        ]

# AssetPlugin
    def get_assets(self):
        return dict(
            js=["js/print_queue.js"]
    )

# Data Persistence
    def _writeConfigurationFile(self, config):
        try:
            import yaml
            from octoprint.util import atomic_write
            with atomic_write(self._print_queue_file_path) as f:
                yaml.safe_dump(config, stream=f, default_flow_style=False, indent="  ", allow_unicode=True)
        except:
            self._logger.info("PQ: error writing configuration file")
        else:
            self._configuration_dict = config

    def _getConfigurationFile(self):
        result_dict = None
        if os.path.exists(self._print_queue_file_path):
            with open(self._print_queue_file_path, "r") as f:
                try:
                    import yaml
                    result_dict = yaml.safe_load(f)
                except:
                    self._logger.info("PQ: error loading configuration file")
                else:
                    if not result_dict:
                        result_dict = dict()
        else:
            result_dict = dict()
        self._configuration_dict = result_dict
        return result_dict

    def print_completion_script(self, comm, script_type, script_name, *args, **kwargs):
        if script_type == "gcode" and script_name == "afterPrintDone" and len(self.printqueue) > 0:
            prefix = self._configuration_dict["bed_clear_script"]
            postfix = None
            return prefix, postfix
        else:
            return None

    # Event Handling
    def on_event(self, event, payload):
        self._logger.info("on_event fired: " + event)
        if event == "FileSelected":
            self._plugin_manager.send_plugin_message(self._identifier, dict(message="file_selected",file=payload["path"]))
            self._logger.info(payload)
            self.selected_file = payload["path"]
        if event == "PrinterStateChanged":
            state = self._printer.get_state_id()
            self._logger.info("printer state: " + state)
            if state  == "OPERATIONAL" and len(self.printqueue) > 0:

                # First make robot clean the plate
                WAIT = 3

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("169.254.126.59", 30002))                            # IP and Port of Robot
                time.sleep(0.5)

                self._logger.info( "_ROBOT: Set output 1 and 2 high")
                s.send ("set_digital_out(1,True)" + "\n")
                time.sleep(0.1)
                s.send ("set_digital_out(2,True)" + "\n")
                time.sleep(2)

                self._logger.info ("_ROBOT: Robot starts Moving!")

                self._logger.info ("_ROBOT: Home position")
                s.send ("movej([0.0, -1.5707963267948966, -1.5707963267948966, -1.5707963267948966, 1.5707963267948966, 0.0], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: About to pic from printer")
                s.send ("movej([0.7642796794483169, -2.1642082724729685, -1.641482161500667, -2.4511404015008362, 0.7668976733263083, 1.538682268558201], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Pick from printer")
                s.send ("movel([0.16266468628587152, -2.070833157491272, -1.8107790989441168, -2.2931881041953495, 0.16667894356545848, 1.4494959437812907], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                # close gripper

                self._logger.info ("_ROBOT: Up from pick from printer")
                s.send ("movel([0.16266468628587152, -1.9519762354304582, -1.727003294848389, -2.490584842595908, 0.16667894356545848, 1.4442599560253078], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Holding plate")
                s.send ("movel([0.9583602922700863, -2.2698006922186256, -1.2007865253720986, -2.7900833422381353, 0.9594074898212829, 1.5447909209401811], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: About to place plate")
                s.send ("movej([1.9116591297093892, -2.075196480621258, -1.7455037849195292, -2.467895562319982, -1.2470377505499486, 1.5468853160425742], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Place plate")
                s.send ("movel([1.911135530933791, -2.3464206463811768, -1.8065903087393307, -2.1350612739646633, -1.2479104151759457, 1.5449654538653805], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                # open gripper

                self._logger.info ("_ROBOT: About to place plate")
                s.send ("movej([1.9116591297093892, -2.075196480621258, -1.7455037849195292, -2.467895562319982, -1.2470377505499486, 1.5468853160425742], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: About to pic new plate")
                s.send ("movel([1.1468558514854739, -2.4399702942880728, -1.074773753378108, -2.7757716423717818, -2.014459022651855, 1.5409511965857936], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Pick new plate")
                s.send ("movel([1.146506785635075, -2.6624997739173497, -1.1383037381507017, -2.4902357767455094, -2.0149826214274533, 1.539903999034597], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                # close gripper

                self._logger.info ("_ROBOT: About to pic new plate")
                s.send ("movel([1.1468558514854739, -2.4399702942880728, -1.074773753378108, -2.7757716423717818, -2.014459022651855, 1.5409511965857936], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Holding plate")
                s.send ("movej([0.9583602922700863, -2.2698006922186256, -1.2007865253720986, -2.7900833422381353, 0.9594074898212829, 1.5447909209401811], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Up from pick from printer")
                s.send ("movel([0.16266468628587152, -1.9519762354304582, -1.727003294848389, -2.490584842595908, 0.16667894356545848, 1.4442599560253078], 1.0, 0.5)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Pick from printer")
                s.send ("movel([0.16266468628587152, -2.070833157491272, -1.8107790989441168, -2.2931881041953495, 0.16667894356545848, 1.4494959437812907], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                # open gripper

                self._logger.info ("_ROBOT: About to pic from printer")
                s.send ("movel([0.7642796794483169, -2.1642082724729685, -1.641482161500667, -2.4511404015008362, 0.7668976733263083, 1.538682268558201], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Home position")
                s.send ("movej([0.0, -1.5707963267948966, -1.5707963267948966, -1.5707963267948966, 1.5707963267948966, 0.0], 1.0, 1)" + "\n")
                time.sleep(WAIT)

                self._logger.info ("_ROBOT: Set output 1 and 2 low")
                s.send ("set_digital_out(1,False)" + "\n")
                time.sleep(0.1)
                s.send ("set_digital_out(2,False)" + "\n")
                time.sleep(0.1)

                # ..and then proceed with printing
                self._printer.select_file(self.uploads_dir + self.printqueue[0], False, True)
                self.printqueue.pop(0)
            if state == "OFFLINE" or state == "CANCELLING" or state == "CLOSED" or state == "ERROR" or state == "CLOSED_WITH_ERROR":
                self._logger.info("deleting print queue")
                self.printqueue = []
                self.s.close()
        return

__plugin_name__ = "Print Queue"
def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PrintQueuePlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.scripts": __plugin_implementation__.print_completion_script,
    }
