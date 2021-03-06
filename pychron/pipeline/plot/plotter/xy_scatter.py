# ===============================================================================
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
# ===============================================================================

# ============= enthought library imports =======================

# ============= standard library imports ========================
from __future__ import absolute_import
from numpy import array
# ============= local library imports  ==========================
from uncertainties import nominal_value
# from pychron.processing.plotters.xy.xy_scatter_tool import XYScatterTool
from pychron.pipeline.plot.plotter.arar_figure import BaseArArFigure


class XYScatter(BaseArArFigure):
    def build(self, plots):
        graph = self.graph
        # plots = (pp for pp in plots if self._has_attr(pp.name))
        padding = self.options.paddings()
        for i, po in enumerate(plots):
            p = graph.new_plot(ytitle=po.ytitle, xtitle=po.xtitle, padding=padding)

            p.value_range.tight_bounds = False
            self._setup_plot(i, p, po)

    def plot(self, plots, legend=None):
        if plots:
            # self.xs = self._get_xs(plots, self.sorted_analyses)
            # with graph.no_regression(refresh=True):
            # plots = [po for po in plots if po.use]
            for i, po in enumerate(plots):
                if po.name == 'Ratio':
                    self._plot_ratio(po, i)
                elif po.name == 'Scatter':
                    self._plot_scatter(po, i)
                elif po.name == 'TimeSeries':
                    self._plot_series(po, i)

                    # self.xmi, self.xma = self.min_x(), self.max_x()
                    # self.xpad = '0.1'

    def _plot_ratio(self, po, i):
        xs = [nominal_value(ai) for ai in self._unpack_attr(po.xtitle)]
        ys = [nominal_value(ai) for ai in self._unpack_attr(po.ytitle)]

        args = self.graph.new_series(x=array(xs), y=array(ys),
                                     # display_index=ArrayDataSource(data=n),
                                     # plotid=pid,
                                     add_inspector=False,
                                     marker=po.marker,
                                     marker_size=po.marker_size)

    def _plot_scatter(self, po, i):
        pass

    def _plot_series(self, po, i):
        pass

#
# class XYScatterEditor(GraphEditor):
#     """
#         this class is a hybridized version of a FigureEditor and a BaseArArFigure
#         in the future separate the editor and plotting similar to an IdeogramEditor e.i make a XYScatter(BaseArArFigure)
#         that handles the plotting
#
#
#     """
#     update_graph_on_set_items = True
#     tool = None
#     plotter_options_manager = Instance(XYScatterOptionsManager, ())
#
#     def rebuild(self):
#         self.rebuild_graph()
#
#     def load_fits(self, refiso):
#         pass
#
#     def load_tool(self, tool=None):
#         pass
#
#     def dump_tool(self):
#         pass
#
#     def _normalize(self, vs, scalar):
#         vs -= vs[0]
#         return vs / scalar
#
#     def _pretty(self, v):
#         if v == 'uage':
#             v = 'Age'
#         elif v == 'uage_wo_j_err':
#             v = 'Age w/o Jerr'
#         elif '_' in v:
#             v = ' '.join(map(str.capitalize, v.split('_')))
#         return v
#
#     def _rebuild_graph(self):
#
#         options = self.plotter_options_manager.plotter_options
#         if options.datasource == 'Database':
#             self._rebuild_database_graph(options)
#         else:
#             self._rebuild_file_graph(options)
#
#     def _rebuild_file_graph(self, options):
#         g = self.graph
#         g.new_plot()
#
#         i_attr = options.index_attr
#         v_attr = options.value_attr
#
#         parser = options.get_parser()
#         xs, ys = parser.get_values((i_attr, v_attr))
#         self.plot_series(g, options, xs, ys)
#
#     def plot_series(self, g, options, xs, ys):
#         kw = options.get_marker_dict()
#         fit = options.fit
#         fit = fit if fit != NULL_STR else False
#         args = g.new_series(x=xs, y=ys, fit=fit, type='scatter',
#                             add_inspector=False, **kw)
#         if fit:
#             plot, scatter, line = args
#         else:
#             scatter, plot = args
#         return scatter
#
#     def _rebuild_database_graph(self, options):
#         ans = self.analyses
#         if ans:
#             g = self.graph
#             g.new_plot()
#
#             i_attr = options.index_attr
#             v_attr = options.value_attr
#
#             if i_attr == 'timestamp' or v_attr == 'timestamp':
#                 ans = sorted(ans, key=lambda x: x.timestamp)
#
#             uxs = [ai.get_value(i_attr) for ai in ans]
#             uys = [ai.get_value(v_attr) for ai in ans]
#             xs = array([nominal_value(ui) for ui in uxs])
#             ys = array([nominal_value(ui) for ui in uys])
#             eys = array([std_dev(ui) for ui in uys])
#             exs = array([std_dev(ui) for ui in uxs])
#
#             if i_attr == 'timestamp':
#                 xtitle = 'Normalized Analysis Time'
#                 xs = self._normalize(xs, options.index_time_scalar)
#             else:
#                 xtitle = i_attr
#
#             if v_attr == 'timestamp':
#                 ytitle = 'Normalized Analysis Time'
#                 ys = self._normalize(ys, options.value_time_scalar)
#             else:
#                 ytitle = v_attr
#
#             ytitle = self._pretty(ytitle)
#             xtitle = self._pretty(xtitle)
#
#             scatter = self.plot_series(g, options, xs, ys)
#
#             scatter.yerror = ArrayDataSource(eys)
#             scatter.xerror = ArrayDataSource(exs)
#
#             self._add_scatter_inspector(scatter, ans)
#
#             if options.index_error:
#
#                 n = options.index_nsigma
#                 self._add_error_bars(scatter, exs, 'x', n, end_caps=options.index_end_caps)
#                 xmn, xmx = min(xs - exs), max(xs + exs)
#             else:
#                 xmn, xmx = min(xs), max(xs)
#
#             if options.value_error:
#
#                 n = options.value_nsigma
#                 self._add_error_bars(scatter, eys, 'y', n, end_caps=options.value_end_caps)
#                 ymn, ymx = min(ys - eys * n), max(ys + eys * n)
#             else:
#                 ymn, ymx = min(ys), max(ys)
#
#             g.set_x_limits(xmn, xmx, pad='0.1')
#             g.set_y_limits(ymn, ymx, pad='0.1')
#
#             g.set_x_title(xtitle)
#             g.set_y_title(ytitle)
#             g.refresh()
#
#     def _index_info(self):
#         options = self.plotter_options_manager.plotter_options
#         i_attr = options.index_attr
#         fi_attr = self._pretty(i_attr)
#
#         def func(i, x, y, ai):
#             uv = ai.get_value(i_attr)
#             v = nominal_value(uv)
#             e = std_dev(uv)
#             pe = format_percent_error(v, e)
#             return '{}= {}+/-{}({}%)'.format(fi_attr, floatfmt(v), floatfmt(e), pe)
#
#         return func
#
#     def _add_scatter_inspector(self, scatter, ans, value_format=None):
#         broadcaster = BroadcasterTool()
#         scatter.tools.append(broadcaster)
#
#         rect_tool = RectSelectionTool(scatter)
#         rect_overlay = RectSelectionOverlay(component=scatter,
#                                             tool=rect_tool)
#
#         scatter.overlays.append(rect_overlay)
#         broadcaster.tools.append(rect_tool)
#
#         if value_format is None:
#             value_format = lambda x: '{:0.5f}'.format(x)
#
#         # value_format=self._value_info()
#         additional_info = self._index_info()
#         point_inspector = AnalysisPointInspector(scatter,
#                                                  analyses=ans,
#                                                  convert_index=lambda x: '{:0.3f}'.format(x),
#                                                  value_format=value_format,
#                                                  additional_info=additional_info)
#
#         pinspector_overlay = PointInspectorOverlay(component=scatter,
#                                                    tool=point_inspector)
#
#         scatter.overlays.append(pinspector_overlay)
#         broadcaster.tools.append(point_inspector)
#
#     def _add_error_bars(self, scatter, errors, axis, nsigma,
#                         end_caps,
#                         visible=True):
#         ebo = ErrorBarOverlay(component=scatter,
#                               orientation=axis,
#                               nsigma=nsigma,
#                               visible=visible,
#                               use_end_caps=end_caps)
#
#         scatter.underlays.append(ebo)
#         setattr(scatter, '{}error'.format(axis), ArrayDataSource(errors))
#         return ebo

# ============= EOF =============================================
