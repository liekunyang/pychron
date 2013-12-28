#===============================================================================
# Copyright 2013 Jake Ross
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
import os
from traits.api import on_trait_change
from pyface.tasks.task_layout import TaskLayout, VSplitter, PaneItem, \
    HSplitter, Tabbed
#============= standard library imports ========================
#============= local library imports  ==========================
from pychron.core.helpers.filetools import add_extension
from pychron.core.helpers.iterfuncs import partition
from pychron.paths import r_mkdir
from pychron.processing.tasks.analysis_edit.interpolation_task import InterpolationTask, no_auto_ctx, bin_analyses
from zobs.wx.gui import invoke_in_main_thread


class IntercalibrationFactorTask(InterpolationTask):
    id = 'pychron.analysis_edit.ic_factor'
    ic_factor_editor_count = 1
    name = 'Detector Intercalibration'

    def _default_layout_default(self):
        return TaskLayout(
            id='pychron.analysis_edit.ic_factor',
            left=HSplitter(
                PaneItem('pychron.browser'),
                VSplitter(
                    Tabbed(PaneItem('pychron.analysis_edit.unknowns'),
                           PaneItem('pychron.analysis_edit.references')),
                    PaneItem('pychron.analysis_edit.controls'),
                )
            )
        )

    def new_ic_factor(self):
        from pychron.processing.tasks.detector_calibration.intercalibration_factor_editor import IntercalibrationFactorEditor

        editor = IntercalibrationFactorEditor(name='ICFactor {:03n}'.format(self.ic_factor_editor_count),
                                              processor=self.manager
        )
        self._open_editor(editor)
        self.ic_factor_editor_count += 1

        #selector = self.manager.db.selector
        #self.unknowns_pane.items = selector.records[156:159]
        #self.references_pane.items = selector.records[150:155]

    @on_trait_change('active_editor:tool:[analysis_type]')
    def _handle_analysis_type(self, obj, name, old, new):
        if name == 'analysis_type':
            records = self.unknowns_pane.items
            if records is None:
                records = self.analysis_table.selected

            if records:
                ans = self._load_references(records, new)
                ans = self.manager.make_analyses(ans)
                self.references_pane.items = ans

    def do_easy_ic(self):
        self._do_easy_func()

    def _easy_func(self, ep, manager):
        print ep, manager
        db = self.manager.db

        doc = ep.doc('ic')
        fits = doc['fits']
        projects = doc['projects']

        unks = [ai for proj in projects
                for si in db.get_samples(project=proj)
                for ln in si.labnumbers
                for ai in ln.analyses]

        prog = manager.progress
        prog.increase_max(len(unks))

        preceding_fits, non_preceding_fits = map(list, partition(fits, lambda x: x['fit'] == 'preceding'))
        if preceding_fits:
            self.debug('preceding fits for ic_factors not implemented')
            # for ai in unks:
            #     if prog.canceled:
            #         return
            #     elif prog.accepted:
            #         break
            #     l, a, s = ai.labnumber.identifier, ai.aliquot, ai.step
            #     prog.change_message('Save preceding blank for {}-{:02n}{}'.format(l, a, s))
            #     hist = db.add_history(ai, 'blanks')
            #     ai.selected_histories.selected_blanks = hist
            #     for fi in preceding_fits:
            #         self._preceding_correct(db, fi, ai, hist)

        #make figure root dir
        if doc['save_figures']:
            root = doc['figure_root']
            r_mkdir(root)

        if non_preceding_fits:
            with no_auto_ctx(self.active_editor):
                for ais in bin_analyses(unks):
                    if prog.canceled:
                        return
                    elif prog.accepted:
                        break

                    self.active_editor.set_items(ais, progress=prog)
                    self.active_editor.find_references(progress=prog)

                    #refresh graph
                    invoke_in_main_thread(self.active_editor.rebuild_graph)

                    if not manager.wait_for_user():
                        return

                    #save a figure
                    if doc['save_figures']:
                        title = self.active_editor.make_title()
                        p = os.path.join(root, add_extension(title, '.pdf'))
                        self.active_editor.save_file(p)

                    self.active_editor.save(progress=prog)
                    self.active_editor.dump_tool()

        return True

#============= EOF =============================================
