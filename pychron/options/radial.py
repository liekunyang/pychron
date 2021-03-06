# ===============================================================================
# Copyright 2017 ross
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
from __future__ import absolute_import

from traits.api import List

from pychron.options.aux_plot import AuxPlot
from pychron.options.options import AgeOptions
from pychron.options.views.radial_views import VIEWS
from pychron.pychron_constants import NULL_STR


class RadialAuxPlot(AuxPlot):
    names = List([NULL_STR, 'Radial'], transient=True)
    # names = List([NULL_STR, 'Analysis Number Nonsorted', 'Analysis Number',
    #               'Radiogenic 40Ar', 'K/Ca', 'K/Cl', 'Mol K39', 'Ideogram'])
    # _plot_names = List(['', 'analysis_number_nonsorted', 'analysis_number', 'radiogenic_yield',
    #                     'kca', 'kcl', 'moles_k39', 'relative_probability'])


class RadialOptions(AgeOptions):
    subview_names = List(['Main', 'Radial', 'Appearance', 'Calculations', 'Display', 'Groups'],
                         transient=True)
    aux_plot_klass = RadialAuxPlot

    def _get_subview(self, name):
        return VIEWS[name]
# ============= EOF =============================================
