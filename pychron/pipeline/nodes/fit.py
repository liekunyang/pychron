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
from itertools import groupby

from numpy import inf
from pyface.confirmation_dialog import confirm
from pyface.constant import YES
from six.moves import zip
from traits.api import Bool, List, HasTraits, Str, Float, Instance

from pychron.core.progress import progress_loader
from pychron.options.options_manager import BlanksOptionsManager, ICFactorOptionsManager, \
    IsotopeEvolutionOptionsManager, \
    FluxOptionsManager
from pychron.options.views.views import view
from pychron.pipeline.editors.flux_results_editor import FluxResultsEditor
from pychron.pipeline.editors.results_editor import IsoEvolutionResultsEditor
from pychron.pipeline.nodes.figure import FigureNode
from pychron.pipeline.state import get_detector_set
from pychron.pychron_constants import NULL_STR


class RefitException(BaseException):
    pass


class FitNode(FigureNode):
    use_save_node = Bool(True)
    _fits = List
    _keys = List

    # has_save_node = False

    def _set_saveable(self, state):
        ps = self.plotter_options.get_saveable_aux_plots()
        state.saveable_keys = [p.name for p in ps]
        state.saveable_fits = [p.fit for p in ps]

    def _get_valid_unknowns(self, unks):
        if self.plotter_options.analysis_types:
            unks = [u for u in unks if not u.is_omitted() and u.analysis_type in self.plotter_options.analysis_types]
        return unks

    def check_refit(self, unks):
        unks = self._get_valid_unknowns(unks)
        for ui in unks:
            try:
                if self._check_refit(ui):
                    break

            except RefitException:
                return False
        else:
            if confirm(None, self._refit_message) == YES:
                return True

    def _check_refit(self, ai):
        pass


class FitReferencesNode(FitNode):
    basename = None
    auto_set_items = False

    def run(self, state):
        po = self.plotter_options

        self._fits = list(reversed([pi for pi in po.get_loadable_aux_plots()]))
        self._keys = [fi.name for fi in self._fits]
        unks = self._get_valid_unknowns(state.unknowns)
        if self.check_refit(unks):
            return

        super(FitReferencesNode, self).run(state)
        if state.canceled:
            return

        # self.plotter_options.set_detectors(state.union_detectors)
        if state.references:
            key = lambda x: x.group_id
            for i, (gid, refs) in enumerate(groupby(sorted(state.references, key=key), key=key)):
                if i == 0:
                    editor = self.editor
                else:
                    editor = self._editor_factory()
                    state.editors.append(editor)

                unks = [u for u in unks if u.group_id == gid]
                editor.set_items(unks, compress=False)
                if self.plotter_options.use_restricted_references:
                    refas = self._get_reference_analysis_types()
                    if refas:
                        refs = [r for r in refs if r.analysis_type in refas]

                editor.set_references(list(refs))

        self._set_saveable(state)
        self.editor.force_update(force=True)

    def _get_reference_analysis_types(self):
        return []


class FitBlanksNode(FitReferencesNode):
    editor_klass = 'pychron.pipeline.plot.editors.blanks_editor,BlanksEditor'
    plotter_options_manager_klass = BlanksOptionsManager
    name = 'Fit Blanks'
    basename = 'Blanks'
    _refit_message = 'The selected Isotopes have already been fit for blanks. Would you like to skip refitting?'

    def _check_refit(self, ai):
        for k in self._keys:
            i = ai.get_isotope(k)
            if not i.blank.reviewed:
                return True

    def _get_reference_analysis_types(self):
        return ['blank_{}'.format(a) for a in self.plotter_options.analysis_types]

    def _options_view_default(self):
        return view('Blanks Options')

    def _configure_hook(self):
        pom = self.plotter_options_manager
        if self.unknowns:
            unk = self.unknowns[0]
            names = unk.isotope_keys
            if names:
                names = [NULL_STR] + names
                pom.set_names(names)

            atypes = list({a.analysis_type for a in self.unknowns})
            pom.set_analysis_types(atypes)


ATTRS = ('numerator', 'denominator', 'standard_ratio', 'analysis_type')


class FitICFactorNode(FitReferencesNode):
    editor_klass = 'pychron.pipeline.plot.editors.intercalibration_factor_editor,' \
                   'IntercalibrationFactorEditor'
    plotter_options_manager_klass = ICFactorOptionsManager
    name = 'Fit ICFactor'
    basename = 'ICFactor'

    predefined = List
    _refit_message = 'The selected IC Factors have already been fit. Would you like to skip refitting?'

    def _get_reference_analysis_types(self):
        return ['air', 'cocktail']

    def _options_view_default(self):
        return view('ICFactor Options')

    def _configure_hook(self):
        udets = get_detector_set(self.unknowns)
        rdets = get_detector_set(self.references)
        dets = list(udets.union(rdets))
        self.plotter_options_manager.set_detectors(dets)

    # def set_detectors(self, dets):
    #     self.plotter_options_manager.set_detectors(dets)

    def _set_saveable(self, state):
        super(FitICFactorNode, self)._set_saveable(state)
        ps = self.plotter_options.get_saveable_aux_plots()
        state.saveable_keys = [p.denominator for p in ps]

    # def run(self, state):
    #     super(FitICFactorNode, self).run(state)

    def _check_refit(self, ai):
        for k in self._keys:
            num, dem = k.split('/')
            i = ai.get_isotope(detector=dem)
            if i is not None:
                if not i.ic_factor_reviewed:
                    return True
            else:
                from pyface.message_dialog import warning
                warning(None, 'Data for detector {} is missing from {}'.format(dem, ai.record_id))
                raise RefitException()

    def load(self, nodedict):
        try:
            fits = nodedict['fits']
        except KeyError as e:
            return

        pom = self.plotter_options_manager
        self.plotter_options = pom.selected_options
        self.plotter_options.set_aux_plots(fits)

    def _to_template(self, d):
        d['fits'] = [{'numerator': a.numerator,
                      'denominator': a.denominatior,
                      'standard_ratio': a.standard_ratio,
                      'analysis_type': a.analysis_type}
                     for a in self.plotter_options.aux_plots]


GOODNESS_TAGS = ('int_err', 'slope', 'outlier', 'curvature', 'rsquared')
GOODNESS_NAMES = ('Intercept Error', 'Slope', 'Outliers', 'Curvature', 'RSquared')
INVERTED_GOODNESS = ('rsquared',)


class IsoEvoResult(HasTraits):
    # record_id = Str
    isotope = Str
    n = Str
    fit = Str
    intercept_value = Float
    intercept_error = Float
    percent_error = Float
    regression_str = Str
    int_err_goodness = None
    slope_goodness = None
    outlier_goodness = None
    curvature_goodness = None
    rsquared_goodness = None

    int_err_threshold = None
    slope_threshold = None
    outlier_threshold = None
    curvature_threshold = None
    rsquared_threshold = None

    int_err = None
    slope = None
    outlier = None
    curvature = None
    rsquared = None

    analysis = Instance('pychron.processing.analyses.analysis.Analysis')

    @property
    def goodness(self):
        good = True
        for g in GOODNESS_TAGS:
            v = getattr(self, '{}_goodness'.format(g))
            if v is not None:
                good &= v

        return good

    @property
    def tooltip(self):

        def f(t, m):
            v = getattr(self, '{}_goodness'.format(t))
            if v is not None:
                comp = '<' if t in INVERTED_GOODNESS else '>'
                v = 'OK' if v else "Bad {}{}{}".format('{}'.format(t), comp, '{}_threshold'.format(t))
            else:
                v = 'Not Tested'
            return '{:<25}: {}'.format(m, v)

        return '\n'.join([f(g, n) for g, n in zip(GOODNESS_TAGS, GOODNESS_NAMES)])

    @property
    def record_id(self):
        r = ''
        if self.analysis:
            r = self.analysis.record_id
        return r

    @property
    def identifier(self):
        r = ''
        if self.analysis:
            r = self.analysis.identifier
        return r


class FitIsotopeEvolutionNode(FitNode):
    editor_klass = 'pychron.pipeline.plot.editors.isotope_evolution_editor,' \
                   'IsotopeEvolutionEditor'
    plotter_options_manager_klass = IsotopeEvolutionOptionsManager
    name = 'Fit IsoEvo'
    use_plotting = False
    _refit_message = 'The selected Isotope Evolutions have already been fit. Would you like to skip refitting?'

    def _check_refit(self, analysis):
        for k in self._keys:

            i = analysis.get_isotope(k)
            if i is None:
                i = analysis.get_isotope(detector=k)

            if i is None:
                print('invalid isotope "{}"'.format(k), analysis.isotope_keys)
                continue

            if not i.reviewed:
                return True

    def _options_view_default(self):
        return view('Iso Evo Options')

    def _configure_hook(self):
        pom = self.plotter_options_manager
        if self.unknowns:
            unk = self.unknowns[0]
            names = unk.isotope_keys
            if names:
                dets = unk.detector_keys
                if dets:
                    names.extend(dets)
                pom.set_names(names)

            atypes = list({a.analysis_type for a in self.unknowns})
            pom.set_analysis_types(atypes)

    def run(self, state):
        super(FitIsotopeEvolutionNode, self).run(state)

        po = self.plotter_options

        self._fits = list(reversed([pi for pi in po.get_loadable_aux_plots()]))
        self._keys = [fi.name for fi in self._fits]

        unks = self._get_valid_unknowns(state.unknowns)
        if unks:
            if self.check_refit(unks):
                return

            fs = progress_loader(unks, self._assemble_result, threshold=1, step=10)

            if self.editor:
                self.editor.analysis_groups = [(ai,) for ai in unks]

            # for ai in state.unknowns:
            #     ai.graph_id = 0

            self._set_saveable(state)
            if fs:
                e = IsoEvolutionResultsEditor(fs)
                e.plotter_options = po
                state.editors.append(e)

    def _assemble_result(self, xi, prog, i, n):
        if prog:
            prog.change_message('Load raw data {}'.format(xi.record_id))

        fits = self._fits
        xi.load_raw_data(self._keys)

        xi.set_fits(fits)
        isotopes = xi.isotopes
        for f in fits:
            k = f.name
            if k in isotopes:
                iso = isotopes[k]
            else:
                iso = xi.get_isotope(detector=k, kind='baseline')

            if iso:
                i, e = iso.value, iso.error
                try:
                    pe = abs(e / i * 100)
                except ZeroDivisionError:
                    pe = inf

                goodness_threshold = f.goodness_threshold
                int_err_goodness = None
                if goodness_threshold:
                    int_err_goodness = bool(e < goodness_threshold)

                slope = None
                slope_goodness = None
                slope_threshold = None
                if f.slope_goodness:
                    if f.slope_goodness_intensity < i:
                        slope_threshold = f.slope_goodness
                        slope = iso.get_slope()
                        slope_goodness = bool(slope < 0 or slope < slope_threshold)

                outliers = None
                outliers_threshold = None
                outlier_goodness = None
                if f.outlier_goodness:
                    outlier = iso.noutliers()
                    outliers_threshold = f.outlier_goodness
                    outlier_goodness = bool(outlier < f.outlier_goodness)

                curvature_goodness = None
                curvature = None
                curvature_threshold = None
                if f.curvature_goodness:
                    curvature = iso.get_curvature(f.curvature_goodness_at)
                    curvature_threshold = f.curvature_goodness
                    curvature_goodness = curvature < curvature_threshold

                nstr = str(iso.n)
                if iso.noutliers():
                    nstr = '{}({})'.format(iso.n - iso.noutliers(), nstr)

                rsquared_goodness = None
                rsquared = 0
                rsquared_threshold = 0
                if f.rsquared_goodness:
                    rsquared = iso.rsquared_adj
                    rsquared_threshold = f.rsquared_goodness
                    rsquared_goodness = rsquared > rsquared_threshold

                yield IsoEvoResult(analysis=xi,
                                   nstr=nstr,
                                   intercept_value=i,
                                   intercept_error=e,
                                   percent_error=pe,
                                   int_err=i,
                                   int_err_threshold=goodness_threshold,
                                   int_err_goodness=int_err_goodness,

                                   slope=slope,
                                   slope_threshold=slope_threshold,
                                   slope_goodness=slope_goodness,

                                   outliers=outliers,
                                   outliers_threshold=outliers_threshold,
                                   outlier_goodness=outlier_goodness,

                                   curvature=curvature,
                                   curvature_threshold=curvature_threshold,
                                   curvature_goodness=curvature_goodness,

                                   rsquared=rsquared,
                                   rsquared_threshold=rsquared_threshold,
                                   rsquared_goodness=rsquared_goodness,

                                   regression_str=iso.regressor.tostring(),
                                   fit=iso.fit,
                                   isotope=k)


class FitFluxNode(FitNode):
    name = 'Fit Flux'
    editor_klass = FluxResultsEditor
    plotter_options_manager_klass = FluxOptionsManager

    def _options_view_default(self):
        return view('Flux Options')

    def run(self, state):
        super(FitFluxNode, self).run(state)
        editor = self.editor
        if not editor:
            state.canceled = True
            return

        self.name = 'Fit Flux {}'.format(state.irradiation, state.level)
        geom = state.geometry
        monitors = state.flux_monitors

        if monitors:
            po = self.plotter_options
            # lk = po.lambda_k
            # state.decay_constants = {'lambda_k_total': lk, 'lambda_k_total_error': 0}
            # state.error_calc_method = po.
            # state.flux_fit = po.
            state.flux_options = po

            editor.plotter_options = po
            editor.geometry = geom
            editor.irradiation = state.irradiation
            editor.level = state.level
            editor.holder = state.holder

            editor.set_positions(monitors, state.unknown_positions)
            state.saveable_irradiation_positions = editor.monitor_positions + state.unknown_positions
            editor.predict_values()

# ============= EOF =============================================
