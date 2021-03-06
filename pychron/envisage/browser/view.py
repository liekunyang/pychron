# ===============================================================================
# Copyright 2015 Jake Ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================

# ============= enthought library imports =======================
from traits.api import HasTraits, Str, Instance, Button, Bool
from traitsui.api import View, UItem, HGroup, VGroup, Group, spring, Handler, EnumEditor

from pychron.core.ui.custom_label_editor import CustomLabel
from pychron.envisage.browser.sample_view import BrowserSampleView, BrowserInterpretedAgeView
from pychron.envisage.browser.time_view import TimeViewModel
from pychron.envisage.icon_button_editor import icon_button_editor


# class AnalysisGroupAdapter(BrowserAdapter):
#     all_columns = [('Name', 'name'),
#                    ('Created', 'create_date'),
#                    ('Modified', 'last_modified')]
#
#     columns = [('Name', 'name'),
#                ('Create Date', 'create_date'),
#                ('Modified', 'last_modified')]
#

class BrowserViewHandler(Handler):
    def pane_append_button_changed(self, info):
        info.ui.context['pane'].is_append = True
        info.ui.dispose(True)

    def pane_replace_button_changed(self, info):
        info.ui.context['pane'].is_append = False
        info.ui.dispose(True)


class BaseBrowserView(HasTraits):
    name = 'Browser'
    id = 'pychron.browser'
    multi_select = True
    analyses_defined = Str('1')

    sample_view = Instance(BrowserSampleView)
    time_view = Instance(TimeViewModel)

    model = Instance(HasTraits)

    def trait_context(self):
        """ Use the model object for the Traits UI context, if appropriate.
        """
        if self.model:
            return {'object': self.model, 'pane': self}
        return super(BaseBrowserView, self).trait_context()

    def _get_browser_tool_group(self):
        hgrp = HGroup(icon_button_editor('filter_by_button',
                                         'find',
                                         tooltip='Search for analyses using defined criteria'),
                      icon_button_editor('advanced_filter_button', 'magnifier',
                                         tooltip='Advanced Search. e.g. search by intensity'),
                      icon_button_editor('load_recent_button', 'edit-history-2', tooltip='Load recent analyses'),
                      icon_button_editor('find_references_button',
                                         '3d_glasses',
                                         tooltip='Find references associated with current selection'),
                      # icon_button_editor('toggle_view',
                      #                    'arrow_switch',
                      #                    tooltip='Toggle between Sample and Time views'),
                      icon_button_editor('refresh_selectors_button', 'arrow_refresh',
                                         tooltip='Refresh the database selectors e.g PI, Project, Load, Irradiation, etc'),
                      UItem('object.dvc.data_source', editor=EnumEditor(name='object.dvc.data_sources')),
                      spring,
                      CustomLabel('datasource_url', color='maroon'),
                      show_border=True)
        return hgrp

    def _get_browser_group(self):
        grp = Group(UItem('pane.sample_view',
                          style='custom',
                          visible_when='sample_view_active'),
                    UItem('time_view_model',
                          style='custom',
                          visible_when='not sample_view_active'))
        return grp

    def _sample_view_default(self):
        return BrowserSampleView(model=self.model, pane=self)


class StandaloneBrowserView(BaseBrowserView):
    def traits_view(self):
        main_grp = self._get_browser_group()

        hgrp = HGroup(icon_button_editor('filter_by_button',
                                         'find',
                                         tooltip='Filter analyses using defined criteria'),
                      icon_button_editor('toggle_view',
                                         'arrow_switch',
                                         tooltip='Toggle between Sample and Time views'),
                      spring,
                      CustomLabel('datasource_url', color='maroon'),
                      show_border=True)

        v = View(VGroup(hgrp, main_grp),
                 buttons=['OK', 'Cancel'],
                 title='Standalone Browser',
                 width=-900,
                 resizable=True)

        return v


class PaneBrowserView(BaseBrowserView):
    def traits_view(self):
        main_grp = self._get_browser_group()

        tool_grp = self._get_browser_tool_group()

        v = View(VGroup(tool_grp, main_grp))

        return v


class BrowserView(BaseBrowserView):
    is_append = False

    append_button = Button('Append')
    replace_button = Button('Replace')
    show_append_replace_buttons = Bool(True)

    def traits_view(self):
        main_grp = self._get_browser_group()
        tool_grp = self._get_browser_tool_group()

        bgrp = HGroup(spring, UItem('pane.append_button'), UItem('pane.replace_button'),
                      defined_when='pane.show_append_replace_buttons')
        v = View(VGroup(tool_grp, main_grp, bgrp),
                 handler=BrowserViewHandler(),
                 title='Browser',
                 width=1200,
                 resizable=True)

        return v


class InterpretedAgeBrowserView(HasTraits):
    append_button = Button('Append')
    replace_button = Button('Replace')
    sample_view = Instance(BrowserInterpretedAgeView)

    def _sample_view_default(self):
        return BrowserInterpretedAgeView(model=self.model, pane=self)

    def trait_context(self):
        """ Use the model object for the Traits UI context, if appropriate.
        """
        if self.model:
            return {'object': self.model, 'pane': self}
        return super(InterpretedAgeBrowserView, self).trait_context()

    def traits_view(self):
        bgrp = HGroup(spring, UItem('pane.append_button'), UItem('pane.replace_button'))
        v = View(VGroup(UItem('pane.sample_view', style='custom'),
                        bgrp),
                 handler=BrowserViewHandler(),
                 title='Browser',
                 width=900,
                 resizable=True)

        return v

# ============= EOF =============================================
