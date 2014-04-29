#===============================================================================
# Copyright 2014 Jake Ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#===============================================================================

#============= enthought library imports =======================
from traits.api import Instance, Button, Bool, Str, List, provides

#============= standard library imports ========================
#============= local library imports  ==========================
from pychron.external_pipette.protocol import IPipetteManager
from pychron.hardware.apis_controller import ApisController
from pychron.managers.manager import Manager


class InvalidPipetteError(BaseException):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'Invalid Pipette name={}'.format(self.name)

    def __str__(self):
        return repr(self)


@provides(IPipetteManager)
class SimpleApisManager(Manager):
    apis_controller = Instance(ApisController)

    test_command = Str(auto_set=False, enter_set=True)
    test_command_response = Str
    clear_test_response_button = Button
    test_button = Button
    testing = Bool
    test_script_button = Button

    available_pipettes = List
    available_blanks = List

    #for unittesting
    _timeout_flag = False

    def set_extract_state(self, state):
        pass

    def finish_loading(self):
        blanks = self.apis_controller.get_available_blanks()
        airs = self.apis_controller.get_available_airs()
        if blanks:
            self.available_blanks = blanks.split(',')
        if airs:
            self.available_pipettes = airs.split(',')

    def bind_preferences(self, prefid):
        pass

    def load_pipette(self, *args, **kw):
        func = 'load_pipette'
        return self._load_pipette(func, *args, **kw)

    def load_blank(self, *args, **kw):
        func = 'load_blank'
        return self._load_pipette(func, *args, **kw)

    #private
    def _load_pipette(self, func, name, timeout=10, period=1):
        name = str(name)
        if not name in self.available_pipettes:
            raise InvalidPipetteError(name)

        func = getattr(self.apis_controller, func)
        func(name)

        #wait for completion
        return self._loading_complete(timeout=timeout, period=period)

    def _loading_complete(self, **kw):
        if self._timeout_flag:
            return True
        else:
            return self.apis_controller.blocking_poll('get_loading_complete', **kw)

    def _test_script_button_fired(self):
        self.testing = True
        from pychron.pyscripts.extraction_line_pyscript import ExtractionPyScript

        e = ExtractionPyScript(manager=self)
        e.setup_context(extract_device='')
        e.extract_pipette(self.available_pipettes[0], timeout=3)
        self.testing = False

    def _test_commmand_changed(self):
        self._execute_test_command()

    def _test_button_fired(self):
        self._execute_test_command()

    def _execute_test_command(self):
        cmd = self._assemble_command()
        if cmd:
            r = self.apis_controller.ask(cmd)
            r = r if r else 'No Response'
            self.test_command_response = '{}\n{}>>{}'.format(self.test_command_response, cmd, r)

    def _assemble_command(self):
        cmd = self.test_command
        if cmd.strip().endswith(','):
            return

        return cmd


    def _apis_controller_default(self):
        v = ApisController(name='apis_controller')
        return v

        # class ApisManager(Manager):
        #     implements(IPipetteManager)
        #     controller = Instance(ApisController)
        #
        #     available_pipettes = List(['1', '2'])
        #
        #     #testing buttons
        #     test_load_1 = Button('Test Load 1')
        #     testing = Bool
        #     test_result = Str
        #
        #     test_script_button = Button('Test Script')
        #
        #     reload_canvas_button = Button('Reload Canvas')
        #
        #     _timeout_flag = False
        #     canvas = Instance('pychron.canvas.canvas2D.extraction_line_canvas2D.ExtractionLineCanvas2D')
        #     valve_manager = Instance('pychron.extraction_line.valve_manager.ValveManager')
        #     mode = 'normal'
        #
        #     def finish_loading(self):
        #         from pychron.extraction_line.valve_manager import ValveManager
        #
        #         vm = ValveManager(extraction_line_manager=self)
        #         vm.load_valves_from_file('apis_valves.xml')
        #         for v in vm.valves.values():
        #             v.actuator = self.controller
        #
        #         self.valve_manager = vm
        #         for p in vm.pipette_trackers:
        #             p.load()
        #             self._set_pipette_counts(p.name, p.counts)
        #
        #     def open_valve(self, name, **kw):
        #         return self._change_valve_state(name, 'normal', 'open')
        #
        #     def close_valve(self, name, **kw):
        #         return self._change_valve_state(name, 'normal', 'close')
        #
        #     def set_selected_explanation_item(self, name):
        #         pass
        #
        #
        #
        #     def set_extract_state(self, state):
        #         pass
        #
        #     def load_pipette(self, name, timeout=10, period=1):
        #         name = str(name)
        #         if not name in self.available_pipettes:
        #             raise InvalidPipetteError(name)
        #
        #         self.controller.load_pipette(name)
        #
        #         #wait for completion
        #         return self._loading_complete(timeout=timeout, period=period)
        #
        #     #private
        #     def _loading_complete(self, **kw):
        #         if self._timeout_flag:
        #             return True
        #         else:
        #             return self.controller.blocking_poll('get_loading_status', **kw)
        #
        #     #testing buttons
        #     def _test_load_1_fired(self):
        #         self.debug('Test load 1 fired')
        #         self.testing = True
        #         self.test_result = ''
        #         try:
        #             ret = self.load_pipette('1', timeout=3)
        #             self.test_result = 'OK'
        #         except (TimeoutError, InvalidPipetteError), e:
        #             self.test_result = str(e)
        #         # self.test_result = 'OK' if ret else 'Failed'
        #         self.testing = False
        #
        #     def _test_script_button_fired(self):
        #         self.testing = True
        #         from pychron.pyscripts.extraction_line_pyscript import ExtractionPyScript
        #
        #         e = ExtractionPyScript(manager=self)
        #         e.setup_context(extract_device='')
        #         e.extract_pipette(1, timeout=3)
        #         self.testing = False


        # def _change_valve_state(self, name, mode, action):
        #     result, change = False, False
        #     func = getattr(self.valve_manager, '{}_by_name'.format(action))
        #     ret = func(name, mode=mode)
        #     if ret:
        #         result, change = ret
        #         if isinstance(result, bool):
        #             if change:
        #                 self.canvas.update_valve_state(name, True if action == 'open' else False)
        #                 self.canvas.request_redraw()
        #
        #     return result, change
        #
        # def _set_pipette_counts(self, name, value):
        #     c = self.canvas
        #     obj = c.scene.get_item('vlabel_{}'.format(name))
        #     if obj is not None:
        #         obj.value = value
        #         c.request_redraw()
        # def _load_canvas(self, c):
        #     c.load_canvas_file('apis_canvas_config.xml',
        #                        setup_name='apis_canvas')
        # @on_trait_change('valve_manager:pipette_trackers:counts')
        # def _update_pipette_counts(self, obj, name, old, new):
        #     self._set_pipette_counts(obj.name, new)
        #
        # def _reload_canvas_button_fired(self):
        #     self._load_canvas(self.canvas)
        #     self.canvas.request_redraw()
        #
        # def _canvas_default(self):
        #     from pychron.canvas.canvas2D.extraction_line_canvas2D import ExtractionLineCanvas2D
        #
        #     c = ExtractionLineCanvas2D(manager=self)
        #     self._load_canvas(c)
        #     return c

#============= EOF =============================================

