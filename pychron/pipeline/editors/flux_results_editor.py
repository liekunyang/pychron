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

from itertools import groupby
from operator import attrgetter

from numpy import array, zeros, vstack, linspace, meshgrid, arctan2, sin, cos
# ============= enthought library imports =======================
from traits.api import HasTraits, Str, Int, Bool, Float, Property, List, Instance, Event, Button
from traitsui.api import View, UItem, TableEditor, VGroup, HGroup, Item, spring, Tabbed, Readonly
from traitsui.extras.checkbox_column import CheckboxColumn
from traitsui.table_column import ObjectColumn
from uncertainties import nominal_value, std_dev, ufloat

from pychron.core.helpers.formatting import calc_percent_error, floatfmt
from pychron.core.regression.flux_regressor import PlaneFluxRegressor, BowlFluxRegressor
from pychron.core.stats import calculate_weighted_mean, calculate_mswd
from pychron.core.stats.monte_carlo import FluxEstimator
from pychron.envisage.icon_button_editor import icon_button_editor
from pychron.envisage.tasks.base_editor import BaseTraitsEditor
from pychron.graph.contour_graph import ContourGraph
from pychron.graph.error_bar_overlay import ErrorBarOverlay
from pychron.graph.error_envelope_overlay import ErrorEnvelopeOverlay
from pychron.graph.graph import Graph
from pychron.graph.tools.analysis_inspector import AnalysisPointInspector
from pychron.pipeline.editors.irradiation_tray_overlay import IrradiationTrayOverlay
from pychron.pipeline.plot.plotter.arar_figure import SelectionFigure
from pychron.processing.argon_calculations import calculate_flux
from pychron.pychron_constants import MSEM, SD
from pychron.pychron_constants import PLUSMINUS_ONE_SIGMA


def mean_j(ans, error_kind, monitor_age, lambda_k):
    js = [calculate_flux(ai.uF, monitor_age, lambda_k=lambda_k) for ai in ans]

    fs = [nominal_value(fi) for fi in js]
    es = [std_dev(fi) for fi in js]

    av, werr = calculate_weighted_mean(fs, es)

    mswd = None
    if error_kind == SD:
        n = len(fs)
        werr = (sum((av - fs) ** 2) / (n - 1)) ** 0.5
    elif error_kind == MSEM:
        mswd = calculate_mswd(fs, es)
        werr *= (mswd ** 0.5 if mswd > 1 else 1)

    j = ufloat(av, werr)

    if mswd is None:
        mswd = calculate_mswd(fs, es)

    return j, mswd


def omean_j(ans, error_kind, monitor_age, lambda_k):
    # ufs = (ai.uF for ai in ans)
    # fs, es = zip(*((fi.nominal_value, fi.std_dev)
    #                for fi in ufs))
    fs = [nominal_value(ai.uF) for ai in ans]
    es = [std_dev(ai.uF) for ai in ans]

    av, werr = calculate_weighted_mean(fs, es)

    if error_kind == SD:
        n = len(fs)
        werr = (sum((av - fs) ** 2) / (n - 1)) ** 0.5
    elif error_kind == MSEM:
        mswd = calculate_mswd(fs, es)
        werr *= (mswd ** 0.5 if mswd > 1 else 1)

    # reg.trait_set(ys=fs, yserr=es)
    # uf = (reg.predict([0]), reg.predict_error([0]))
    uf = (av, werr)
    j = calculate_flux(uf, monitor_age, lambda_k=lambda_k)

    # print monitor_age, age_equation(j, uf, lambda_k=lambda_k, scalar=1)

    mswd = calculate_mswd(fs, es)
    return j, mswd


def make_grid(r, n):
    xi = linspace(-r, r, n)
    yi = linspace(-r, r, n)
    return meshgrid(xi, yi)


def add_inspector(scatter, func):
    from pychron.graph.tools.point_inspector import PointInspector
    from pychron.graph.tools.point_inspector import PointInspectorOverlay

    point_inspector = PointInspector(scatter, additional_info=func)
    pinspector_overlay = PointInspectorOverlay(component=scatter,
                                               tool=point_inspector)

    scatter.overlays.append(pinspector_overlay)
    scatter.tools.append(point_inspector)


def add_analysis_inspector(scatter, items, add_selection=True, value_format=None, convert_index=None):
    from chaco.tools.broadcaster import BroadcasterTool
    from pychron.graph.tools.rect_selection_tool import RectSelectionTool
    from pychron.graph.tools.rect_selection_tool import RectSelectionOverlay
    from pychron.graph.tools.point_inspector import PointInspectorOverlay

    broadcaster = BroadcasterTool()
    scatter.tools.append(broadcaster)
    if add_selection:
        rect_tool = RectSelectionTool(scatter)
        rect_overlay = RectSelectionOverlay(component=scatter,
                                            tool=rect_tool)

        scatter.overlays.append(rect_overlay)
        broadcaster.tools.append(rect_tool)

    if value_format is None:
        value_format = lambda x: '{:0.5f}'.format(x)

    if convert_index is None:
        convert_index = lambda x: '{:0.3f}'.format(x)

    point_inspector = AnalysisPointInspector(scatter,
                                             analyses=items,
                                             convert_index=convert_index,
                                             # index_tag=index_tag,
                                             # index_attr=index_attr,
                                             value_format=value_format)
    # additional_info=additional_info)

    pinspector_overlay = PointInspectorOverlay(component=scatter,
                                               tool=point_inspector)

    scatter.overlays.append(pinspector_overlay)
    broadcaster.tools.append(point_inspector)

    # u = lambda a, b, c, d: self.update_graph_metadata(a, b, c, d)
    # scatter.index.on_trait_change(self.update_graph_metadata, 'metadata_changed')


class FluxPosition(HasTraits):
    hole_id = Int
    identifier = Str
    sample = Str
    x = Float
    y = Float
    z = Float
    theta = Float
    saved_j = Float
    saved_jerr = Float

    mean_j = Float
    mean_jerr = Float
    mean_j_mswd = Float

    n = Int

    j = Float(enter_set=True, auto_set=False)
    jerr = Float(enter_set=True, auto_set=False)
    use = Bool(True)
    save = Bool(True)
    dev = Float

    percent_saved_error = Property
    percent_mean_error = Property
    percent_pred_error = Property

    analyses = List
    error_kind = Str
    monitor_age = Float
    lambda_k = Float
    was_altered = Bool

    def set_mean_j(self):

        ans = [a for a in self.analyses if not a.is_omitted()]
        if ans:
            j, mswd = mean_j(ans, self.error_kind, self.monitor_age, self.lambda_k)
            self.mean_j = nominal_value(j)
            self.mean_jerr = std_dev(j)
            self.mean_j_mswd = mswd

        self.n = len(ans)

    def _get_percent_saved_error(self):
        return calc_percent_error(self.saved_j, self.saved_jerr)

    def _get_percent_mean_error(self):
        if self.mean_jerr and self.mean_jerr:
            return calc_percent_error(self.mean_j, self.mean_jerr)

    def _get_percent_pred_error(self):
        if self.j and self.jerr:
            return calc_percent_error(self.j, self.jerr)


class FluxResultsEditor(BaseTraitsEditor, SelectionFigure):
    geometry = List
    monitor_positions = List
    unknown_positions = List
    positions = List

    analyses = List
    graph = Instance('pychron.graph.graph.Graph')
    # flux_visualization = Instance('pychron.processing.flux_visualization3D.FluxVisualization3D', ())
    _regressor = None

    levels = 10
    show_labels = False

    color_map_name = 'jet'
    marker_size = Int(2)

    save_all_button = Event
    save_unknowns_button = Event
    recalculate_button = Button('Calculate')

    max_j = Float
    min_j = Float
    percent_j_change = Property
    # j_gradient = Property
    plotter_options = None
    irradiation = Str
    level = Str
    holder = Str

    suppress_metadata_change = Bool(False)
    # scene = Instance(MlabSceneModel, ())

    def set_items(self, analyses):
        if self.geometry:
            self.set_positions(analyses)
            self.predict_values()

    def _recalculate_button_fired(self):
        self.predict_values()

    def set_positions(self, monitors, unk=None):
        self.debug('setting positions mons={}, unks={}'.format(len(monitors), len(unk) if unk else 0))
        opt = self.plotter_options
        monage = opt.monitor_age * 1e6
        lk = opt.lambda_k
        ek = opt.error_kind

        key = attrgetter('identifier')
        geom = self.geometry
        poss = []
        ans = []
        slope = True
        prev = None
        for identifier, ais in groupby(sorted(monitors, key=key), key=key):

            ais = list(ais)
            n = len(ais)

            ref = ais[0]
            j = ref.j
            ip = ref.irradiation_position
            sample = ref.sample

            x, y, r, idx = geom[ip - 1]
            # mj = mean_j(ais, ek, monage, lk)

            p = FluxPosition(identifier=identifier,
                             irradiation=self.irradiation,
                             level=self.level,
                             sample=sample, hole_id=ip,
                             saved_j=nominal_value(j),
                             saved_jerr=std_dev(j),
                             # mean_j=nominal_value(mj),
                             # mean_jerr=std_dev(mj),
                             error_kind=ek,
                             monitor_age=monage,
                             analyses=ais,
                             lambda_k=lk,
                             x=x, y=y,
                             n=n)
            # ans.extend(ais)
            p.set_mean_j()
            poss.append(p)
            if prev:
                slope = prev < p.j
            prev = p.j
            aa, xx, yy, es = self._sort_individuals(p, monage, lk, slope)
            ans.extend(aa)

        self.monitor_positions = poss
        self.analyses = ans
        if unk is not None:
            self.unknown_positions = unk
            # self.positions = mon + unk

    def predict_values(self, refresh=False):
        self.debug('predict values {}'.format(refresh))
        try:
            x, y, z, ze = array([(pos.x, pos.y, pos.mean_j, pos.mean_jerr)
                                 for pos in self.monitor_positions
                                 if pos.use]).T

        except ValueError as e:
            self.debug('no monitor positions to fit, {}'.format(e))
            return

        n = x.shape[0]
        if n >= 3:
            # n = z.shape[0] * 10
            r = max((max(abs(x)), max(abs(y))))
            # r *= 1.25
            reg = self._regressor_factory(x, y, z, ze)
            self._regressor = reg
        else:
            msg = 'Not enough monitor positions. At least 3 required. Currently only {} active'.format(n)
            self.debug(msg)
            self.information_dialog(msg)
            return

        options = self.plotter_options
        if options.use_monte_carlo:
            # from pychron.core.stats.monte_carlo import monte_carlo_error_estimation
            fe = FluxEstimator(options.monte_carlo_ntrials, reg, options.position_only, options.position_error)

            for positions in (self.unknown_positions, self.monitor_positions):
                pts = array([[p.x, p.y] for p in positions])
                nominals, errors = fe.estimate(pts)
                # nominals = reg.predict(pts)
                # errors = monte_carlo_error_estimation(reg, nominals, pts,
                #                                       position_only=self.plotter_options.position_only,
                #                                       position_error=self.plotter_options.position_error,
                #
                #                                       # mean_position_only=self.plotter_options.position_only,
                #                                       # mean_position_error=self.plotter_options.position_error,
                #                                       ntrials=self.plotter_options.monte_carlo_ntrials)

                for p, j, je in zip(positions, nominals, errors):
                    oj = p.saved_j

                    p.j = j
                    p.jerr = je

                    p.dev = (oj - j) / j * 100
        else:
            for positions in (self.unknown_positions, self.monitor_positions):
                for p in positions:
                    j = reg.predict([(p.x, p.y)])[0]
                    je = reg.predict_error([[(p.x, p.y)]])[0]
                    oj = p.saved_j

                    p.j = float(j)
                    p.jerr = float(je)

                    p.dev = (oj - j) / j * 100

        if options.plot_kind == '2D':
            self._graph_contour(x, y, z, r, reg, refresh)
        else:
            self._graph_hole_vs_j(x, y, r, reg, refresh)

    def _graph_contour(self, x, y, z, r, reg, refresh):

        g = self.graph
        if not isinstance(g, ContourGraph):
            g = ContourGraph(container_dict={'kind': 'h',
                                             'bgcolor': self.plotter_options.bgcolor})
            self.graph = g
        else:
            g.clear()

        p = g.new_plot(xtitle='X', ytitle='Y')

        ito = IrradiationTrayOverlay(component=p,
                                     geometry=self.geometry,
                                     show_labels=self.show_labels)
        self.irradiation_tray_overlay = ito
        p.overlays.append(ito)

        gx, gy, m, me = self._model_flux(reg, r)
        # self._visualization_update(gx, gy, m, me, reg.xs, reg.ys)

        s, p = g.new_series(z=m,
                            xbounds=(-r, r),
                            ybounds=(-r, r),
                            levels=self.levels,
                            cmap=self.color_map_name,
                            colorbar=True,
                            style='contour')
        g.add_colorbar(s)

        # pts = vstack((x, y)).T
        s = g.new_series(x, y,
                         z=z,
                         style='cmap_scatter',
                         color_mapper=s.color_mapper,
                         marker='circle',
                         marker_size=self.marker_size)
        self.cmap_scatter = s[0]

    # def _visualization_update(self, gx, gy, z, ze, xs, ys):
    #     gx, gy = gx.T, gy.T
    #
    #     x, y = xs.T
    #
    #     self.scene.mlab.points3d(x, y, ys)
    #     self.scene.mlab.surf(z)
    #     # self.scene.mlab.surf(gx, gy, z-ze, warp_scale='auto')
    #     # self.scene.mlab.surf(gx, gy, z+ze, warp_scale='auto')
    #     # self.scene.mlab.test_points3d()

    def _additional_info(self, ind):
        fm = self.monitor_positions[ind]
        return ['Pos: {}'.format(fm.hole_id),
                'Identifier: {}'.format(fm.identifier)]

    def _graph_hole_vs_j(self, x, y, r, reg, refresh):

        sel = [i for i, a in enumerate(self.analyses) if a.is_omitted()]

        g = self.graph
        if not isinstance(g, Graph):
            g = Graph(container_dict={'bgcolor': self.plotter_options.bgcolor})
            self.graph = g

        po = self.plotter_options

        xs = arctan2(x, y)
        ys = reg.ys
        a = max((abs(min(xs)), abs(max(xs))))
        fxs = linspace(-a, a)

        a = r * sin(fxs)
        b = r * cos(fxs)
        pts = vstack((a, b)).T

        fys = reg.predict(pts)
        yserr = reg.yserr

        # if self.plotter_options.use_weighted_fit:
            # l, u = reg.calculate_error_envelope(pts, rmodel=fys)
        # else:
        l, u = reg.calculate_error_envelope(fxs, rmodel=fys)

        lyy = ys - yserr
        uyy = ys + yserr

        if not refresh:
            g.clear()
            p = g.new_plot(xtitle='Hole (Theta)',
                           ytitle='J',
                           # padding=[90, 5, 5, 40],
                           padding=po.paddings())
            p.bgcolor = po.plot_bgcolor
            g.add_limit_tool(p, 'x')
            g.add_limit_tool(p, 'y')
            g.add_axis_tool(p, p.x_axis)
            g.add_axis_tool(p, p.y_axis)

            p.y_axis.tick_label_formatter = lambda x: floatfmt(x, n=2, s=4, use_scientific=True)

            # plot fit line
            # plot0 == line
            line, _p = g.new_series(fxs, fys)

            ee = ErrorEnvelopeOverlay(component=line,
                                      xs=fxs, lower=l, upper=u)
            line.error_envelope = ee
            line.underlays.append(ee)

            # plot the individual analyses
            # plot1 == scatter
            iscatter, iys = self._graph_individual_analyses()

            # plot means
            # plot2 == scatter
            scatter, _ = g.new_series(xs, ys,
                                      yerror=yserr,
                                      type='scatter',
                                      marker_size=4, marker='diamond')

            ebo = ErrorBarOverlay(component=scatter,
                                  orientation='y')
            scatter.underlays.append(ebo)
            scatter.error_bars = ebo

            add_inspector(scatter, self._additional_info)

            # s.index.metadata_changed = True

            ymi = min(lyy.min(), min(iys))
            yma = max(uyy.max(), max(iys))
            g.set_x_limits(-3.5, 3.5)

            # set metadata last because it will trigger a refresh
            self.suppress_metadata_change = True
            iscatter.index.metadata['selections'] = sel
            self.suppress_metadata_change = False

        else:
            plot = g.plots[0]
            s1 = plot.plots['plot2'][0]
            s1.yerror.set_data(yserr)
            s1.error_bars.invalidate()

            l1 = plot.plots['plot0'][0]
            l1.error_envelope.trait_set(xs=fxs, lower=l, upper=u)
            l1.error_envelope.invalidate()

            g.set_data(ys, plotid=0, series=2, axis=1)
            g.set_data(fys, plotid=0, series=0, axis=1)

            s2 = plot.plots['plot1'][0]
            iys = s2.value.get_data()
            ymi = min(fys.min(), lyy.min(), iys.min())
            yma = max(fys.max(), uyy.max(), iys.max())

            s2.index.metadata['selections'] = sel

        g.set_y_limits(ymi, yma, pad='0.1')
        self._model_sin_flux(fxs, fys)

    def _graph_individual_analyses(self):
        po = self.plotter_options
        g = self.graph

        ixs = []
        iys = []
        ies = []
        ans = []
        m, k = po.monitor_age * 1e6, po.lambda_k
        slope = True
        prev = self.monitor_positions[-1].j
        for j, p in enumerate(self.monitor_positions):
            if p.use:
                if prev:
                    slope = prev < p.j
                prev = p.j
                aa, xx, yy, es = self._sort_individuals(p, m, k, slope)
                ans.extend(aa)
                ixs.extend(xx)
                iys.extend(yy)
                ies.extend(es)
                p.slope = slope
                # yy = sorted(yy, reverse=not slope)

                # ans.extend(p.analyses)
                # ixs.extend(xx)
                # iys.extend(yy)
        s, _p = g.new_series(ixs, iys, yerror=ies, type='scatter', marker='circle', marker_size=1.5)

        ebo = ErrorBarOverlay(component=s,
                              orientation='y')
        s.underlays.append(ebo)
        s.error_bars = ebo

        add_analysis_inspector(s, ans)

        self.analyses = ans
        s.index.on_trait_change(self._update_graph_metadata, 'metadata_changed')
        return s, iys

    def _sort_individuals(self, p, m, k, slope):
        pp = arctan2(p.x, p.y)
        xx = linspace(pp - .1, pp + .1, len(p.analyses))
        ys = [a.model_j(m, k) for a in p.analyses]
        yy = [nominal_value(a) for a in ys]
        es = [std_dev(a) for a in ys]

        data = list(zip(p.analyses, xx, yy, es))
        data = sorted(data, key=lambda x: x[2], reverse=not slope)
        return list(zip(*data))

    def _update_graph_metadata(self, obj, name, old, new):
        # print obj, name, old, new
        # print obj.metadata
        if not self.suppress_metadata_change:
            sel = self._filter_metadata_changes(obj, self.analyses, self._recalculate_means)

    def _recalculate_means(self, sel):
        if sel:
            idx = {self.analyses[si].identifier for si in sel}
        else:
            idx = [None]

        for identifier in idx:
            # self.debug('sel:{} idx:{}'.format(sel, idx))
            for p in self.monitor_positions:
                if p.identifier == identifier:
                    # self.debug('recalculate position {} {}, {}'.format(sel, p.hole_id, p.identifier))
                    p.set_mean_j()
                    p.was_altered = True
                elif p.was_altered:
                    # self.debug('was altered recalculate position {} {}, {}'.format(sel, p.hole_id, p.identifier))
                    p.set_mean_j()
                    p.was_altered = False

        self.predict_values(refresh=True)

    def _model_sin_flux(self, fxs, fys):
        self.max_j = fys.max()
        self.min_j = fys.min()

    def _model_flux(self, reg, r):

        n = reg.n * 10
        gx, gy = make_grid(r, n)

        nz = zeros((n, n))
        ne = zeros((n, n))
        for i in range(n):
            pts = vstack((gx[i], gy[i])).T

            nominals = reg.predict(pts)
            nz[i] = nominals

        self.max_j = nz.max()
        self.min_j = nz.min()

        return gx, gy, nz, ne

    def _regressor_factory(self, x, y, z, ze):
        if self.plotter_options.plot_kind == '2D':
            if self.plotter_options.model_kind == 'Bowl':
                # from pychron.core.regression.flux_regressor import BowlFluxRegressor
                klass = BowlFluxRegressor
            else:
                # from pychron.core.regression.flux_regressor import PlaneFluxRegressor
                klass = PlaneFluxRegressor
        else:
            klass = PlaneFluxRegressor

        x = array(x)
        y = array(y)
        xy = vstack((x, y)).T
        wf = self.plotter_options.use_weighted_fit
        # if wf:
        #     ec = 'SD'
        # else:
        ec = self.plotter_options.predicted_j_error_type

        reg = klass(xs=xy, ys=z, yserr=ze,
                    error_calc_type=ec,
                    use_weighted_fit=wf)
        # error_calc_type=self.tool.predicted_j_error_type)
        reg.calculate()
        return reg

    def traits_view(self):
        def column(klass=ObjectColumn, editable=False, **kw):
            return klass(text_font='arial 10', editable=editable, **kw)

        def sciformat(x):
            return '{:0.6E}'.format(x) if x else ''

        cols = [
            column(klass=CheckboxColumn, name='use', label='Use', editable=True, width=30),
            column(klass=CheckboxColumn, name='save', label='Save', editable=True, width=30),
            column(name='hole_id', label='Hole'),
            column(name='identifier', label='Identifier'),
            column(name='sample', label='Sample', width=115),

            # column(name='x', label='X', format='%0.3f', width=50),
            # column(name='y', label='Y', format='%0.3f', width=50),
            # column(name='theta', label=u'\u03b8', format='%0.3f', width=50),

            column(name='n', label='N'),
            column(name='saved_j', label='Saved J',
                   format_func=sciformat),
            column(name='saved_jerr', label=PLUSMINUS_ONE_SIGMA,
                   format_func=sciformat),
            column(name='percent_saved_error',
                   label='%',
                   format_func=lambda x: floatfmt(x, n=2)),
            column(name='mean_j', label='Mean J',
                   format_func=sciformat),
            column(name='mean_jerr', label=PLUSMINUS_ONE_SIGMA,
                   format_func=sciformat),
            column(name='percent_mean_error',
                   label='%',
                   format_func=lambda x: floatfmt(x, n=2) if x else ''),
            column(name='mean_j_mswd',
                   label='MSWD',
                   format_func=lambda x: floatfmt(x, n=2)),
            column(name='j', label='Pred. J',
                   format_func=sciformat,
                   width=75),
            column(name='jerr',
                   format_func=sciformat,
                   label=PLUSMINUS_ONE_SIGMA,
                   width=75),
            column(name='percent_pred_error',
                   label='%',
                   format_func=lambda x: floatfmt(x, n=2) if x else ''),
            column(name='dev', label='dev',
                   format='%0.2f',
                   width=70)]

        unk_cols = [column(klass=CheckboxColumn, name='save', label='Save', editable=True, width=30),
                    column(name='hole_id', label='Hole'),
                    column(name='identifier', label='Identifier'),
                    column(name='sample', label='Sample', width=115),
                    column(name='saved_j', label='Saved J',
                           format_func=sciformat),
                    column(name='saved_jerr', label=PLUSMINUS_ONE_SIGMA,
                           format_func=sciformat),
                    column(name='percent_saved_error',
                           label='%',
                           format_func=lambda x: floatfmt(x, n=2)),
                    column(name='j', label='Pred. J',
                           format_func=sciformat,
                           width=75),
                    column(name='jerr',
                           format_func=sciformat,
                           label=PLUSMINUS_ONE_SIGMA,
                           width=75),
                    column(name='percent_pred_error',
                           label='%',
                           format_func=lambda x: floatfmt(x, n=2) if x else ''),
                    column(name='dev', label='dev',
                           format='%0.2f',
                           width=70)]
        mon_editor = TableEditor(columns=cols, sortable=False,
                                 reorderable=False)

        unk_editor = TableEditor(columns=unk_cols, sortable=False,
                                 reorderable=False)

        pgrp = VGroup(UItem('monitor_positions', editor=mon_editor),
                      UItem('unknown_positions', editor=unk_editor),
                      label='Tables')

        ggrp = UItem('graph', style='custom')
        tgrp = HGroup(UItem('recalculate_button'),
                      Item('min_j', format_str='%0.4e',
                           style='readonly',
                           label='Min. J'),
                      Item('max_j',
                           style='readonly',
                           format_str='%0.4e', label='Max. J'),
                      Item('percent_j_change',
                           style='readonly',
                           format_func=floatfmt,
                           label='Delta J(%)'),
                      Readonly('holder', label='Tray'),
                      # Item('j_gradient',
                      #      style='readonly',
                      #      format_func=floatfmt,
                      #      label='Gradient J(%/cm)'),
                      spring, icon_button_editor('save_unknowns_button', 'dialog-ok-5',
                                                 tooltip='Toggle "save" for unknown positions'),
                      icon_button_editor('save_all_button', 'dialog-ok-apply-5',
                                         tooltip='Toggle "save" for all positions'))
        # v = View(VGroup(ggrp, tgrp, pgrp))

        # vgrp = VGroup(UItem('scene', editor=SceneEditor(scene_class=MayaviScene)))
        v = View(VGroup(tgrp, Tabbed(ggrp, pgrp)))
        return v

    def _get_percent_j_change(self):
        maj, mij = self.max_j, self.min_j
        try:
            return (maj - mij) / maj * 100
        except ZeroDivisionError:
            return 0

# ============= EOF =============================================
