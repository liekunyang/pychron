# ===============================================================================
# Copyright 2011 Jake Ross
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

# =============enthought library imports=======================
from __future__ import absolute_import
from __future__ import print_function
import csv
import math
import os

from chaco.api import OverlayPlotContainer, \
    VPlotContainer, HPlotContainer, GridPlotContainer, \
    BasePlotContainer, Plot, ArrayPlotData
from chaco.array_data_source import ArrayDataSource
from chaco.axis import PlotAxis
from enable.component_editor import ComponentEditor
from numpy import array, hstack, Inf, column_stack
from pyface.timer.api import do_after as do_after_timer
from traits.api import Instance, List, Str, Property, Dict, Event, Bool
from traitsui.api import View, Item, UItem

from pychron.core.helpers.color_generators import colorname_generator as color_generator
from pychron.core.helpers.filetools import add_extension
from pychron.graph.context_menu_mixin import ContextMenuMixin
from pychron.graph.offset_plot_label import OffsetPlotLabel
from .tools.contextual_menu_tool import ContextualMenuTool
import six
from six.moves import map
from six.moves import range
from six.moves import zip

VALID_FONTS = [
    # 'Helvetica',
    'Arial',
    'Lucida Grande',
    # 'Times New Roman',
    'Geneva',
    'Courier']


def name_generator(base):
    i = 0
    while 1:
        n = base + str(i)
        yield n
        i += 1


IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.gif']
DEFAULT_IMAGE_EXT = IMAGE_EXTENSIONS[0]


def fmt(data):
    return ['%0.8f' % d for d in data]


# class Graph(Viewable, ContextMenuMixin):
# class GraphHandler(Handler):
# def init(self, info):
# info.object.ui = info.ui
#
#    def closed(self, info, isok):
#        info.object.closed()


# class Graph(Viewable, ContextMenuMixin):
def get_file_path(action='save as', **kw):
    from pyface.api import FileDialog, OK

    dlg = FileDialog(action=action, **kw)
    if dlg.open() == OK:
        return dlg.path


def add_aux_axis(po, p, title='', color='black'):
    """
    """
    #        from chaco.axis import PlotAxis
    from chaco.axis import PlotAxis

    axis = PlotAxis(p, orientation='right',
                    title=title,
                    axis_line_visible=False,
                    tick_color=color,
                    tick_label_color=color,
                    title_color=color)

    p.underlays.append(axis)
    po.add(p)
    #        po.plots['aux'] = [p]

    po.x_grid.visible = False
    po.y_grid.visible = False


def plot_axis_factory(p, key, normal, **kw):
    if key == 'x':
        m = p.index_mapper
        if normal:
            o = 'bottom'
        else:
            o = 'top'
            kw['tick_label_formatter'] = lambda x: ''
    else:
        if normal:
            o = 'left'
        else:
            o = 'right'
            kw['tick_label_formatter'] = lambda x: ''
        m = p.value_mapper
    from chaco.axis import PlotAxis

    ax = PlotAxis(component=p,
                  mapper=m,
                  orientation=o,
                  axis_line_visible=False,
                  **kw)
    return ax


def plot_factory(legend_kw=None, **kw):
    """
    """
    p = Plot(data=ArrayPlotData(),
             # use_backbuffer=True,
             **kw)

    vis = kw['show_legend'] if 'show_legend' in kw else False

    if not isinstance(vis, bool):
        align = vis
        vis = True
    else:
        align = 'lr'

    p.legend.visible = vis
    p.legend.align = align
    if legend_kw:
        p.legend.trait_set(**legend_kw)

    return p


CONTAINERS = {'v': VPlotContainer, 'h': HPlotContainer, 'g': GridPlotContainer, 'o': OverlayPlotContainer}


def container_factory(**kw):
    """
    """
    if 'kind' in kw:
        kind = kw['kind']
    else:
        kind = 'v'

    # kinds = ['v', 'h', 'g', 'o']
    # containers = [VPlotContainer, HPlotContainer, GridPlotContainer, OverlayPlotContainer]

    # c = containers[kinds.index(kind)]
    c = CONTAINERS.get(kind, VPlotContainer)

    options = dict(
        bgcolor='white',
        padding=5,
        fill_padding=True)

    for k in options:
        if k not in list(kw.keys()):
            kw[k] = options[k]

    container = c(**kw)

    # add some tools
    #        cm=ContextualMenuTool(parent=container,
    #                              component=container
    #                              )
    #        container.tools.append(cm)
    #
    # gt = TraitsTool(component = container)
    # container.tools.append(gt)
    return container


class Graph(ContextMenuMixin):
    """
    """
    name = Str
    plotcontainer = Instance(BasePlotContainer)
    container_dict = Dict
    plots = List(Plot)

    selected_plotid = Property(depends_on='selected_plot')
    selected_plot = Instance(Plot)
    window_title = ''
    window_width = 600
    window_height = 500
    window_x = 500
    window_y = 250

    width = 300
    height = 300
    resizable = True

    line_inspectors_write_metadata = False

    # plot_editor = Any
    # plot_editor_klass = PlotEditor
    # graph_editor = Any
    autoupdate = Bool(False)

    # _title = Str
    # _title_font = None
    # _title_size = None

    _convert_index = None

    # _control = None

    status_text = Str
    # groups = None

    # current_pos = None

    # view_identifier = None

    #    ui = Any
    # close_func = Callable
    x_limits_changed = Event

    xdataname_generators = List
    ydataname_generators = List
    yerdataname_generators = List
    color_generators = List
    series = List
    data_len = List
    data_limits = List

    def __init__(self, *args, **kw):
        """
        """
        super(Graph, self).__init__(*args, **kw)
        self.clear()

        pc = self.plotcontainer
        if self.use_context_menu:
            menu = ContextualMenuTool(parent=self,
                                      component=pc)

            pc.tools.append(menu)

    def set_time_xaxis(self, plotid=None):
        if plotid is None:
            plotid = len(self.plots) - 1

    # def closed(self, *args):
    #     if self.close_func:
    #         self.close_func()

    def update_group_attribute(self, plot, attr, value, dataid=0):
        pass

    def get_plotid_by_ytitle(self, *args, **kw):
        plot = self.get_plot_by_ytitle(*args, **kw)
        if plot is not None:
            return self.plots.index(plot)

    def get_plot_by_ytitle(self, txt, startswith=False):
        """
            iso: str

            return None or Plot with y_axis.title equal to iso
            if startswith is True title only has to start with iso
        """
        txt = str(txt)
        if startswith:
            is_equal = lambda x: x.startswith(txt)
        else:
            is_equal = lambda x: x.__eq__(txt)

        for po in self.plots:
            if is_equal(po.y_axis.title):
                return po
        else:
            print('plot titles txt={} {}'.format(txt, [po.y_axis.title for po in self.plots]))

    def get_num_plots(self):
        """
        """
        return len(self.plots)

    def get_num_series(self, plotid):
        """
        """
        return len(self.series[plotid])

    def get_data(self, plotid=0, series=0, axis=0):
        """

        """
        if isinstance(series, (str, six.text_type)):
            s = series
        else:
            s = self.series[plotid][series][axis]

        p = self.plots[plotid]
        return p.data.get_data(s)

    def get_aux_data(self, plotid=0, series=1):
        plot = self.plots[plotid]

        si = plot.plots['aux{:03d}'.format(series)][0]

        oi = si.index.get_data()
        ov = si.value.get_data()
        return oi, ov

    def save_png(self, path=None):
        """
        """
        self._save(type_='pic', path=path)

    def save_pdf(self, path=None):
        """
        """
        from pychron.core.pdf.save_pdf_dialog import save_pdf
        save_pdf(self.plotcontainer)
        # self._save(type_='pdf', path=path)

    def save(self, path=None):
        """
        """
        self._save(path=path)

    def rescale_x_axis(self):
        # l, h = self.selected_plot.default_index.get_bounds()
        # self.set_x_limits(l, h, plotid=self.selected_plotid)
        r = self.selected_plot.index_range
        r.reset()

    def rescale_y_axis(self):
        r = self.selected_plot.value_range
        r.reset()

    def rescale_both(self):
        self.rescale_x_axis()
        self.rescale_y_axis()

        # self.set_x_limits(l, h, plotid=self.selected_plotid)

    # def export_raw_data(self, path=None, header=None, plotid=0):
    #     """
    #     """
    #     if path is None:
    #         path = self._path_factory()
    #     if path is not None:
    #         self._export_raw_data(path, header, plotid)

    def export_data(self, path=None, plotid=None):
        """
        """
        if path is None:
            path = get_file_path()

        if path is not None:
            path = add_extension(path, '.csv')
            self._export_data(path, plotid)

    def read_xy(self, p, header=False, series=0, plotid=0):
        """
        """
        x = []
        y = []
        with open(p, 'r') as f:
            reader = csv.reader(f)
            if header:
                next(reader)
            for line in reader:
                if line[0].startswith('#'):
                    continue
                if len(line) == 2:
                    x.append(float(line[0]))
                    y.append(float(line[1]))

        self.set_data(x, plotid, series)
        self.set_data(y, plotid, series, axis=1)

    #    def close(self):
    #        '''
    #            close the window
    #        '''
    #        if self.ui is not None:
    #            do_after_timer(1, self.ui.dispose)
    #        self.ui = None

    def remove_rulers(self, plotid=0):
        from pychron.graph.guide_overlay import GuideOverlay

        plot = self.plots[plotid]
        for o in plot.overlays:
            if isinstance(o, GuideOverlay):
                plot.overlays.remove(o)

    def clear_plots(self):
        x = list(range(len(self.plots)))

        self.xdataname_generators = [name_generator('x') for _ in x]
        self.ydataname_generators = [name_generator('y') for _ in x]
        self.yerdataname_generators = [name_generator('yer') for _ in x]

        self.color_generators = [color_generator() for _ in x]
        #         for po in x:

        self.series = [[] for _ in x]
        self.data_len = [[] for _ in x]
        self.data_limits = [[] for _ in x]

        #         print '====== {}'.format(self)
        #         print 'len plots {}'.format(len(self.plots))
        for pi in self.plots:

            #             print 'len pi.renderers {}'.format(len(pi.plots.keys()))
            for k, pp in list(pi.plots.items()):
                for renderer in pp:
                    try:
                        pi.remove(renderer)
                    except RuntimeError:
                        print('failed removing {}'.format(renderer))

                pi.plots.pop(k)
                #             print 'len psss.renderers {}'.format(len(pi.plots.keys()))

        self.clear_data()

    def clear(self, clear_container=True):
        """
        """
        self.clear_plots()

        self.plots = []

        self.xdataname_generators = [name_generator('x')]
        self.ydataname_generators = [name_generator('y')]
        self.yerdataname_generators = [name_generator('yer')]

        self.color_generators = [color_generator()]

        self.series = []
        self.data_len = []
        self.data_limits = []

        if clear_container:
            self.plotcontainer = pc = self.container_factory()
            if self.use_context_menu:
                menu = ContextualMenuTool(parent=self,
                                          component=pc)

                pc.tools.append(menu)

        self.selected_plot = None

    def set_axis_label_color(self, *args, **kw):
        """
        """

        kw['attr'] = 'title'
        self._set_axis_color(*args, **kw)

    def set_axis_tick_color(self, *args, **kw):
        """
        """
        attrs = ['tick_label', 'tick']
        if 'attrs' in kw:
            attrs = kw['attrs']

        for a in attrs:
            kw['attr'] = a
            self._set_axis_color(*args, **kw)

    def set_aux_data(self, x, y, plotid=0, series=1):
        p = self.plots[plotid].plots['aux{:03d}'.format(series)][0]
        p.index.set_data(x)
        p.value.set_data(y)

    def clear_data(self, plotid=None, **kw):
        if plotid is None:
            for i, p in enumerate(self.plots):
                for s in self.series[i]:
                    for k in s:
                        p.data.set_data(k, [])
        else:
            self.set_data([], **kw)

    def set_data(self, d, plotid=0, series=0, axis=0):
        """
        """
        if isinstance(series, int):
            n = self.series[plotid][series]
            series = n[axis]

        self.plots[plotid].data.set_data(series, d)

    def set_axis_traits(self, plotid=0, axis='x', **kw):
        """
        """
        plot = self.plots[plotid]

        attr = getattr(plot, '{}_axis'.format(axis))
        attr.trait_set(**kw)

    def set_grid_traits(self, plotid=0, grid='x', **kw):
        """
        """
        plot = self.plots[plotid]

        attr = getattr(plot, '{}_grid'.format(grid))
        attr.trait_set(**kw)

    def set_series_traits(self, d, plotid=0, series=0):
        """
        """
        plot = self.plots[plotid].plots['plot%i' % series][0]
        plot.trait_set(**d)
        self.plotcontainer.request_redraw()

    def get_series_color(self, plotid=0, series=0):
        if isinstance(series, int):
            series = 'plot{:03d}'.format(series)

        p = self.plots[plotid].plots[series][0]
        return p.color

    #    def set_series_type(self, t, plotid = 0, series = 0):
    #        '''

    #        '''
    #        p = self.plots[plotid]
    #        s = 'plot%i' % series
    #
    #        ss = p.plots[s][0]
    #        x = ss.index.get_data()
    #        y = ss.value.get_data()
    #
    #        p.delplot(s)
    #
    #        series,plot=self.new_series(x = x, y = y, color = ss.color, plotid = plotid, type = t, add = True)
    #        self.plotcontainer.invalidate_and_redraw()
    #        return series
    #        #self.refresh_editor()
    def get_series_label(self, plotid=0, series=0):
        """
        """
        r = ''
        legend = self.plots[plotid].legend
        if isinstance(series, str):
            if series in legend.labels:
                return series
            return

        try:
            r = legend.labels[series]
        except IndexError:
            pass

        return r

    def set_series_label(self, label, plotid=0, series=None):
        """

            A chaco update requires that the legends labels match the keys in the plot dict

            save the plots from the dict
            resave them with label as the key

        """

        legend = self.plots[plotid].legend
        if series is None:
            n = len(list(self.plots[plotid].plots.keys()))
            series = n - 1

        if isinstance(series, int):
            series = 'plot{}'.format(series)

        try:
            legend.labels[series] = label
        except Exception as e:
            legend.labels.append(label)

        try:
            plots = self.plots[plotid].plots[series]
        except KeyError:
            print('set series label plotid={} {}'.format(plotid, list(self.plots[plotid].plots.keys())))
            raise

        self.plots[plotid].plots[label] = plots
        self.plots[plotid].plots.pop(series)

    def clear_legend(self, keys, plotid=0):
        """
        """
        legend = self.plots[plotid].legend
        for key in keys:
            legend.plots.pop(key)

    def set_series_visibility(self, v, plotid=0, series=0):
        """
        """
        p = self.plots[plotid]

        if isinstance(series, int):
            series = 'plot%i' % series

        try:
            p.showplot(series) if v else p.hideplot(series)
            self.plotcontainer.invalidate_and_redraw()
        except KeyError as e:
            print('set series visibility', e, p.series)

    def get_x_limits(self, plotid=0):
        """
        """
        return self._get_limits('index', plotid=plotid)

    def get_y_limits(self, plotid=0):
        """
        """
        return self._get_limits('value', plotid=plotid)

    def set_y_limits(self, min_=None, max_=None, pad=0, plotid=0, **kw):
        """
        """
        mmin, mmax = self.get_y_limits(plotid)

        if min_ is None:
            min_ = mmin
        if max_ is None:
            max_ = mmax

        self._set_limits(min_, max_, 'value', plotid, pad, **kw)

    def set_x_limits(self, min_=None, max_=None, pad=0, plotid=0, **kw):
        """
        """
        if self._set_limits(min_, max_, 'index', plotid, pad, **kw):
            self.x_limits_changed = True

    def set_x_tracking(self, track, plotid=0):
        """
        """
        plot = self.plots[plotid]
        if track:
            plot.index_range.tracking_amount = track
            plot.index_range.high_setting = 'track'
            plot.index_range.low_setting = 'auto'
        else:
            plot.index_range.high_setting = 'auto'
            plot.index_range.low_setting = 'auto'

    def set_y_tracking(self, track, plotid=0):
        """
        """
        plot = self.plots[plotid]
        if track:
            plot.value_range.tracking_amount = track
            plot.value_range.high_setting = 'track'
            plot.value_range.low_setting = 'auto'
        else:
            plot.value_range.high_setting = 'auto'
            plot.value_range.low_setting = 'auto'

    def set_plot_title(self, t, font='modern', size=None, plotid=0):
        p = self.plots[plotid]
        p.title = t

    def set_title(self, t, font='modern', size=None):
        """
        """
        self._title = t

        pc = self.plotcontainer

        if pc.overlays:
            pc.overlays.pop()

        if font not in VALID_FONTS:
            font = 'modern'

        if size is None:
            size = 12
        # self._title_font = font
        # self._title_size = size
        font = '{} {}'.format(font, size)

        from chaco.plot_label import PlotLabel

        pl = PlotLabel(t, component=pc, font=font)
        pc.overlays.append(pl)
        self.redraw()

    def get_x_title(self, plotid=0):
        """
        """
        return self._get_title('y_axis', plotid)

    def get_y_title(self, plotid=0):
        """
        """
        return self._get_title('x_axis', plotid)

    def set_x_title(self, title, plotid=None, **font):
        """
        """
        self._set_title('x_axis', title, plotid, **font)

    def set_y_title(self, title, plotid=None, **font):
        """
        """
        self._set_title('y_axis', title, plotid, **font)

    def add_axis_tool(self, plot, axis):
        from pychron.graph.tools.axis_tool import AxisTool
        t = AxisTool(component=axis)
        plot.tools.append(t)

    def add_limit_tool(self, plot, orientation, handler=None):
        from pychron.graph.tools.limits_tool import LimitsTool
        from pychron.graph.tools.limits_tool import LimitOverlay

        t = LimitsTool(component=plot,
                       orientation=orientation)

        o = LimitOverlay(component=plot, tool=t)

        plot.tools.insert(0, t)
        plot.overlays.append(o)
        if handler:
            t.on_trait_change(handler, 'limits_updated')

    def add_plot_label(self, txt, plotid=0, overlay_position='inside top', hjustify='left', **kw):
        """
        """

        c = self.plots[plotid]

        pl = OffsetPlotLabel(txt,
                             component=c,
                             overlay_position=overlay_position, hjustify=hjustify,
                             **kw)
        c.overlays.append(pl)
        return pl

    def add_data_label(self, x, y, plotid=0):
        """
        """
        from chaco.data_label import DataLabel

        plot = self.plots[plotid]

        label = DataLabel(component=plot, data_point=(x, y),
                          label_position="top left", padding=40,
                          bgcolor="lightgray",
                          border_visible=False)
        plot.overlays.append(label)

    def delplot(self, plotid=0, series=0):
        plot = self.plots[plotid]

        if isinstance(series, int):
            series = 'plot{}'.format(series)
        plot.delplot(series)

    def new_plot(self, add=True, **kw):
        """
        """
        p = plot_factory(**kw)

        self.plots.append(p)
        self.color_generators.append(color_generator())
        self.xdataname_generators.append(name_generator('x'))
        self.ydataname_generators.append(name_generator('y'))
        self.yerdataname_generators.append(name_generator('yer'))

        self.series.append([])

        pc = self.plotcontainer
        if add:
            if not isinstance(add, bool):
                pc.insert(add, p)
            else:
                pc.add(p)

        zoom = kw['zoom'] if 'zoom' in kw else False
        pan = kw['pan'] if 'pan' in kw else False

        tools = []
        if zoom:
            nkw = dict(tool_mode='box',
                       always_on=False)
            if 'zoom_dict' in kw:
                zoomargs = kw['zoom_dict']
                for k in zoomargs:
                    nkw[k] = zoomargs[k]

            from chaco.tools.api import ZoomTool

            zt = ZoomTool(component=p, **nkw)

            p.overlays.append(zt)
            tools.append(zt)

        if pan:
            from .tools.pan_tool import MyPanTool as PanTool

            kwargs = dict(always_on=False)
            if isinstance(pan, str):
                kwargs['constrain'] = True
                kwargs['constrain_direction'] = pan
                kwargs['constrain_key'] = None

            pt = PanTool(p, container=pc, **kwargs)
            tools.append(pt)

        plotid = len(self.plots) - 1

        for t in ['x', 'y']:
            title = '{}title'.format(t)
            if title in kw:
                self._set_title('{}_axis'.format(t), kw[title], plotid)

        p.tools = tools
        return p

    def new_graph(self, *args, **kw):
        """
        """
        raise NotImplementedError

    def new_series(self, x=None, y=None,
                   yer=None,
                   plotid=None,
                   colors=None,
                   color_map_name='hot',
                   marker_size=2,
                   **kw):
        """
        """

        if plotid is None:
            plotid = len(self.plots) - 1

        kw['plotid'] = plotid
        kw['marker_size'] = marker_size
        plotobj, names, rd = self._series_factory(x, y, yer=yer, **kw)

        if 'type' in rd:
            ptype = rd['type']
            if ptype == 'line_scatter':
                plotobj.plot(names,
                             type='scatter', marker_size=2,
                             marker='circle',
                             color=rd['color'],
                             outline_color=rd['color'])
                rd['type'] = 'line'

            elif ptype == 'scatter':
                if 'outline_color' not in rd:
                    rd['outline_color'] = rd['color']
                if 'selection_outline_color' not in rd:
                    rd['selection_outline_color'] = rd['color']

            if ptype == 'cmap_scatter':
                from chaco.default_colormaps import color_map_name_dict

                rd['selection_color'] = rd['color']
                rd['selection_outline_color'] = rd['color']

                rd['color_mapper'] = color_map_name_dict[color_map_name]
                c = self.series[plotid][-1][0].replace('x', 'c')
                self.plots[plotid].data.set_data(c, array(colors))
                names += (c,)

        renderer = plotobj.plot(names, **rd)

        return renderer[0], plotobj

    def auto_update(self, *args, **kw):
        """
        """
        pass

    def add_aux_axis(self, po, p, title='', color='black'):
        """
        """

        axis = PlotAxis(p, orientation='right',
                        title=title,
                        axis_line_visible=False,
                        tick_color=color,
                        tick_label_color=color,
                        title_color=color)

        p.underlays.append(axis)
        po.add(p)

        po.x_grid.visible = False
        po.y_grid.visible = False

    def add_aux_datum(self, datum, plotid=0, series=1, do_after=False):
        """
        """

        # def add():
        plot = self.plots[plotid]

        si = plot.plots['aux{:03d}'.format(series)][0]

        oi = si.index.get_data()
        ov = si.value.get_data()

        si.index.set_data(hstack((oi, [datum[0]])))
        si.value.set_data(hstack((ov, [datum[1]])))

        # if do_after:
        #     do_after_timer(do_after, add)
        # else:
        #     add()

    def add_data(self, data, plotlist=None, **kw):
        """
        """
        if plotlist is None:
            plotlist = range(len(data))

        for pi, d in zip(plotlist, data):
            self.add_datum(d,
                           plotid=pi,
                           **kw)

            #     def add_datum(self, *args, **kw):
            #         invoke_in_main_thread(self._add_datum, *args, **kw)

    def add_bulk_data(self, xs, ys, plotid=0, series=0,
                      ypadding='0.1',
                      update_y_limits=False):
        try:
            names = self.series[plotid][series]
        except IndexError:
            print('adding data', plotid, series, self.series[plotid])

        plot = self.plots[plotid]
        data = plot.data
        for n, ds in ((names[0], xs), (names[1], ys)):
            xx = data.get_data(n)
            xx = hstack((xx, ds))
            data.set_data(n, xx)

        if update_y_limits:
            ys = data[names[1]]
            mi = ys.min()
            ma = ys.max()
            if isinstance(ypadding, str):
                ypad = max(0.1, abs(mi - ma)) * float(ypadding)
            else:
                ypad = ypadding

            mi -= ypad
            ma += ypad
            # # if ymin_anchor is not None:
            # #     mi = max(ymin_anchor, mi)
            #
            self.set_y_limits(min_=mi,
                              max_=ma,
                              plotid=plotid)

    def add_datum(self, datum, plotid=0, series=0,
                  update_y_limits=False,
                  ypadding=10,
                  ymin_anchor=None,
                  #                    do_after=None,
                  **kw):

        #         def add(datum):
        # print 'adding data',plotid, series, len(self.series[plotid])
        try:
            names = self.series[plotid][series]
        except (IndexError, TypeError):
            print('adding datum', plotid, series, self.series[plotid])
            return

        plot = self.plots[plotid]

        if not hasattr(datum, '__iter__'):
            datum = (datum,)

        data = plot.data
        mi, ma = -Inf, Inf
        for i, (name, di) in enumerate(zip(names, datum)):
            d = data.get_data(name)
            nd = hstack((d, di))
            data.set_data(name, nd)

            if i == 1:
                # y values
                mi = min(nd)
                ma = max(nd)

        if update_y_limits:
            if isinstance(ypadding, str):
                ypad = max(0.1, abs(mi - ma)) * float(ypadding)
            else:
                ypad = ypadding
            mi -= ypad
            if ymin_anchor is not None:
                mi = max(ymin_anchor, mi)

            self.set_y_limits(min_=mi,
                              max_=ma + ypad,
                              plotid=plotid)

            #         if do_after:
            #             do_after_timer(do_after, add, datum)
            #         else:
            #             add(datum)

    # def show_crosshairs(self, color='black'):
    #     """
    #     """
    #     self.crosshairs_enabled = True
    #     self._crosshairs_factory(color=color)
    #     self.plotcontainer.request_redraw()
    #
    # def destroy_crosshairs(self):
    #     """
    #     """
    #     self.crosshairs_enabled = False
    #     plot = self.plots[0].plots['plot0'][0]
    #     plot.overlays = [o for o in plot.overlays if not isinstance(o, LineInspector)]
    #     self.plotcontainer.request_redraw()

    def add_range_selector(self, plotid=0, series=0):
        from chaco.tools.range_selection import RangeSelection
        from chaco.tools.range_selection_overlay import RangeSelectionOverlay

        plot = self.plots[plotid].plots['plot{}'.format(series)][0]

        plot.active_tool = RangeSelection(plot, left_button_selects=True)

        plot.overlays.append(RangeSelectionOverlay(component=plot))

    def add_guide(self, value, orientation='h', plotid=0, color=(0, 0, 0)):
        """
        """
        plot = self.plots[plotid]

        from pychron.graph.guide_overlay import GuideOverlay

        guide_overlay = GuideOverlay(component=plot,
                                     value=value,
                                     color=color)
        plot.overlays.append(guide_overlay)

    def _add_rule(self, v, orientation, plotid=0, add_move_tool=False, **kw):
        if v is None:
            return

        if 'plot' in kw:
            plot = kw['plot']
        else:
            plot = self.plots[plotid]

        from pychron.graph.guide_overlay import GuideOverlay, GuideOverlayMoveTool
        l = GuideOverlay(plot, value=v, orientation=orientation, **kw)
        plot.underlays.append(l)

        if add_move_tool:
            plot.tools.append(GuideOverlayMoveTool(overlay=l))

        return l

    def add_vertical_rule(self, v, **kw):
        return self._add_rule(v, 'v', **kw)

    def add_horizontal_rule(self, v, **kw):
        return self._add_rule(v, 'h', **kw)

    def add_opposite_ticks(self, plotid=0, key=None):
        """
        """
        p = self.plots[plotid]
        if key is None:
            for key in ['x', 'y']:
                ax = plot_axis_factory(p, key, False)
                p.underlays.append(ax)

        else:
            ax = plot_axis_factory(p, key, False)
            p.underlays.append(ax)

    def add_minor_xticks(self, plotid=0, **kw):
        """
        """
        p = self.plots[plotid]
        from pychron.graph.minor_tick_overlay import MinorTicksOverlay

        m = MinorTicksOverlay(component=p, orientation='v', **kw)
        p.underlays.append(m)

    def add_minor_yticks(self, plotid=0, **kw):
        """
        """
        p = self.plots[plotid]

        from pychron.graph.minor_tick_overlay import MinorTicksOverlay

        m = MinorTicksOverlay(component=p, orientation='h', **kw)
        p.underlays.append(m)

    def set_time_xaxis(self, plotid=None):
        from chaco.scales_tick_generator import ScalesTickGenerator
        from chaco.scales.time_scale import CalendarScaleSystem

        if plotid is None:
            plotid = len(self.plots) - 1

        p = self.plots[plotid]

        p.x_axis.tick_generator = ScalesTickGenerator(scale=CalendarScaleSystem())

    def refresh(self):
        pass

    def invalidate_and_redraw(self):
        self.plotcontainer._layout_needed = True
        self.plotcontainer.invalidate_and_redraw()

    def redraw(self, force=True):
        """
        """
        if force:
            self.invalidate_and_redraw()
        else:
            self.plotcontainer.request_redraw()

    def get_next_color(self, exclude=None, plotid=0):
        cg = self.color_generators[plotid]

        nc = next(cg)
        if exclude is not None:
            if not isinstance(exclude, (list, tuple)):
                exclude = [exclude]

            while nc in exclude:
                nc = next(cg)

        return nc

    def container_factory(self):
        """
        """
        return container_factory(**self.container_dict)

    # def _add_line_inspector(self, plot, axis='x', color='red'):
    #     """
    #     """
    #     from chaco.tools.line_inspector import LineInspector
    #     plot.overlays.append(LineInspector(component=plot,
    #                                        axis='index_%s' % axis,
    #                                        write_metadata=self.line_inspectors_write_metadata,
    #                                        inspect_mode='indexed',
    #                                        is_listener=False,
    #                                        color=color))

    # def _crosshairs_factory(self, plot=None, color='black'):
    #     """
    #     """
    #     if plot is None:
    #         plot = self.plots[0].plots['plot0'][0]
    #     self._add_line_inspector(plot, axis='x', color=color)
    #     self._add_line_inspector(plot, axis='y', color=color)

    def _export_data(self, path, plotid):
        # names = []
        # a = None
        with open(path, 'w') as wfile:
            def write(l):
                wfile.write('{}\n'.format(l))

            for plot in self.plots:
                line = plot.y_axis.title
                write(line)
                for k, pp in six.iteritems(plot.plots):
                    pp = pp[0]
                    a = column_stack((pp.index.get_data(), pp.value.get_data()))

                    e = getattr(pp, 'yerror', None)

                    header = 'x,y'
                    if e is not None:
                        try:
                            a = column_stack((a, e.get_data()))
                            header = 'x,y,e'
                        except ValueError:
                            pass

                    write(k)
                    write(header)
                    for row in a:
                        write(','.join(map('{:0.8f}'.format, row)))
                        # print 'fff', pp, pp[0].yerror
                        # data = plot.data
                        # names.extend(sorted(data.list_data()))
                        # if a is None:
                        #     a = array(data.get_data(names[0]))
                        #
                        # for ni in names[1:]:
                        #     d = data.get_data(ni)
                        #     try:
                        #         a = column_stack((a, d))
                        #     except ValueError:
                        #         a = column_stack((a, zeros_like(a)))

                        # savetxt(path, a, fmt='%.8f', delimiter=',', header=','.join(names))

                        # if plotid is not None:
                        #     plot = self.plots[plotid]
                        # else:
                        #     plot = self.selected_plot
                        #
                        # if plot is None:
                        #     return
                        #
                        # data = plot.data
                        # names = sorted(data.list_data())
                        #
                        # a = array(data.get_data(names[0]))
                        # for ni in names[1:]:
                        #     d = data.get_data(ni)
                        #     try:
                        #         a = column_stack((a, d))
                        #     except ValueError:
                        #         a = column_stack((a, zeros_like(a)))
                        #
                        # savetxt(path, a, fmt='%.8f', delimiter=',', header=','.join(names))

    def _series_factory(self, x, y, yer=None, plotid=0, add=True, **kw):
        """
        """

        if x is None:
            x = array([])
        if y is None:
            y = array([])

        if 'yerror' in kw:
            if not isinstance(kw['yerror'], ArrayDataSource):
                kw['yerror'] = ArrayDataSource(kw['yerror'])

        yername = None
        plot = self.plots[plotid]
        if add:
            if 'xname' in kw:
                xname = kw['xname']
            else:

                xname = next(self.xdataname_generators[plotid])
            if 'yname' in kw:
                yname = kw['yname']
            else:
                yname = next(self.ydataname_generators[plotid])

            names = (xname, yname)
            #             self.raw_x[plotid].append(x)
            #             self.raw_y[plotid].append(y)
            if yer is not None:
                # self.raw_yer[plotid].append(yer)
                yername = next(self.yerdataname_generators[plotid])
                names += (yername,)
            self.series[plotid].append(names)
        else:
            # try:
            xname = self.series[plotid][0][0]
            yname = self.series[plotid][0][1]
            if yer is not None:
                yername = self.series[plotid][0][2]
                # except IndexError:
                #     pass

        plot.data.set_data(xname, x)
        plot.data.set_data(yname, y)
        if yer is not None:
            plot.data.set_data(yername, yer)

        colorkey = 'color'
        if 'color' not in list(kw.keys()):
            color_gen = self.color_generators[plotid]
            c = next(color_gen)
        else:
            c = kw['color']
        if isinstance(c, str):
            c = c.replace(' ', '')

        if 'type' in kw:
            if kw['type'] == 'bar':
                colorkey = 'fill_color'
            elif kw['type'] == 'polygon':
                colorkey = 'face_color'
                kw['edge_color'] = c
            elif kw['type'] == 'scatter':
                if 'outline_color' not in kw:
                    kw['outline_color'] = c

        for k, v in [
            ('render_style', 'connectedpoints'),
            (colorkey, c),
            ('selection_color', 'white')]:
            if k not in list(kw.keys()):
                kw[k] = v

        return plot, (xname, yname), kw

    def _save(self, type_='pic', path=None):
        """
        """
        if path is None:
            path = get_file_path(default_directory=os.path.expanduser('~'))
            # from pyface.api import FileDialog, OK
            # dlg = FileDialog(action='save as', default_directory=os.path.expanduser('~'))
            # if dlg.open() == OK:
            #     path = dlg.path
            #     self.status_text = 'Image Saved: %s' % path

        if path is not None:
            if type_ == 'pdf' or path.endswith('.pdf'):
                self._render_to_pdf(filename=path)
            else:
                # auto add an extension to the filename if not present
                # extension is necessary for PIL compression
                # set default save type_ DEFAULT_IMAGE_EXT='.png'

                # see http://infohost.nmt.edu/tcc/help/pubs/pil/formats.html
                for ei in IMAGE_EXTENSIONS:
                    if path.endswith(ei):
                        self._render_to_pic(path)
                        break
                else:
                    self._render_to_pic(os.path.join(path, DEFAULT_IMAGE_EXT))

                    #                base, ext = os.path.splitext(path)
                    #
                    #                if not ext in IMAGE_EXTENSIONS:
                    #                    path = ''.join((base, DEFAULT_IMAGE_EXT))

    def _render_to_pdf(self, save=True, canvas=None, filename=None, dest_box=None):
        """
        """
        # save_pdf()
        # from chaco.pdf_graphics_context import PdfPlotGraphicsContext
        #
        # if filename:
        #     # if not filename.endswith('.pdf'):
        #     #     filename += '.pdf'
        #     filename = add_extension(filename, ext='.pdf')
        #
        # gc = PdfPlotGraphicsContext(filename=filename,
        #                             pdf_canvas=canvas,
        #                             dest_box=dest_box)
        # pc = self.plotcontainer
        #
        # # pc.do_layout(force=True)
        # # pc.use_backbuffer=False
        # gc.render_component(pc, valign='center')
        # if save:
        #     gc.save()
        #     # pc.use_backbuffer=True
        #
        # return gc

    def _render_to_pic(self, filename):
        """
        """
        from chaco.plot_graphics_context import PlotGraphicsContext

        p = self.plotcontainer
        gc = PlotGraphicsContext((int(p.outer_width), int(p.outer_height)))
        # p.use_backbuffer = False
        gc.render_component(p)
        # p.use_backbuffer = True
        gc.save(filename)

    def _render_to_clipboard(self):
        '''
            on mac osx the bitmap gets copied to the clipboard
            
            the contents of clipboard are available to Preview and NeoOffice 
            but not Excel
            
            More success may be had on windows 
            
            Copying to clipboard is used to get a Graph into another program
            such as Excel or Illustrator
            
            Save the image as png then Insert Image is probably equivalent but not
            as convenient
            
            not working
        '''

    def _get_title(self, axis, plotid):
        """
        """
        axis = getattr(self.plots[plotid], axis)
        return axis.title

    def _set_title(self, axis, title, plotid, font=None, size=None):
        """
        """
        if plotid is None:
            plotid = len(self.plots) - 1

        axis = getattr(self.plots[plotid], axis)
        params = dict(title=title)
        if font is not None or size is not None:
            if font not in VALID_FONTS:
                font = 'modern'

            tfont = '{} {}'.format(font, size + 2)
            params.update(title_font=tfont)

        axis.trait_set(**params)
        self.plotcontainer.request_redraw()

    def _get_limits(self, axis, plotid):
        """
        """
        plot = self.plots[plotid]
        try:
            ra = getattr(plot, '%s_range' % axis)
            return ra.low, ra.high
        except AttributeError as e:
            print('get_limits', e)

    def _set_limits(self, mi, ma, axis, plotid, pad, pad_style='symmetric', force=False):

        if not plotid < len(self.plots):
            return

        plot = self.plots[plotid]
        ra = getattr(plot, '{}_range'.format(axis))
        scale = getattr(plot, '{}_scale'.format(axis))

        if isinstance(pad, str):
            # interpret pad as a percentage of the range
            # ie '0.1' => 0.1*(ma-mi)
            if ma is None:
                ma = ra.high
            if mi is None:
                mi = ra.low

            if mi == -Inf:
                mi = 0
            if ma == Inf:
                ma = 100

            if ma is not None and mi is not None:
                dev = ma - mi

                def convert(p):
                    p = float(p) * dev
                    if abs(p) < 1e-10:
                        p = 1
                    return p

                if ',' in pad:
                    pad = [convert(p) for p in pad.split(',')]
                else:
                    pad = convert(pad)

            if not pad:
                pad = 0

            if isinstance(mi, (int, float)):
                if isinstance(pad, list):
                    mi -= pad[0]
                elif pad_style in ('symmetric', 'lower'):
                    mi -= pad

            if isinstance(ma, (int, float)):
                if isinstance(pad, list):
                    ma += pad[1]
                elif pad_style in ('symmetric', 'upper'):
                    ma += pad

        if scale == 'log':
            try:
                if mi <= 0:
                    mi = Inf
                    data = plot.data
                    for di in data.list_data():
                        if 'y' in di:
                            ya = sorted(data.get_data(di))

                            i = 0
                            try:
                                while ya[i] <= 0:
                                    i += 1
                                if ya[i] < mi:
                                    mi = ya[i]

                            except IndexError:
                                mi = 0.01

                mi = 10 ** math.floor(math.log(mi, 10))

                ma = 10 ** math.ceil(math.log(ma, 10))
            except ValueError:
                return

        change = False
        if mi is not None:
            change = ra.low != mi
            if isinstance(mi, (int, float)):
                if mi < ra.high:
                    ra.low = mi
            else:
                ra.low = mi

        if ma is not None:
            change = change or ra.high != ma
            if isinstance(ma, (int, float)):
                if ma > ra.low:
                    ra.high = ma
            else:
                ra.high = ma

        if change:
            self.redraw(force=force)
        return change

    def _get_selected_plotid(self):
        r = 0
        if self.selected_plot is not None:
            r = self.plots.index(self.selected_plot)

        return r

    def show(self):
        do_after_timer(1, self.edit_traits)

    def panel_view(self):
        plot = Item('plotcontainer',
                    style='custom',
                    show_label=False,
                    editor=ComponentEditor())

        v = View(plot)
        return v

    def traits_view(self):
        v = View(UItem('plotcontainer',
                       style='custom',
                       editor=ComponentEditor()),
                 title=self.window_title,
                 width=self.window_width,
                 height=self.window_height,
                 x=self.window_x,
                 y=self.window_y,
                 resizable=self.resizable)
        return v


if __name__ == '__main__':
    m = Graph()
    m.new_plot(zoom=True)
    m.new_series([1, 2, 3], [1, 41, 14])
    m.configure_traits()
    # def show(self):
    #     do_after_timer(1, self.edit_traits)
    #
    # def panel_view(self):
    #     plot = Item('plotcontainer',
    #                 style='custom',
    #                 show_label=False,
    #                 editor=ComponentEditor())
    #
    #     v = View(plot)
    #     return v
    #
    # def traits_view(self):
    #     plot = Item('plotcontainer',
    #                 style='custom',
    #                 show_label=False,
    #                 editor=ComponentEditor(
    #                     size=(self.width,
    #                           self.height)))
    #
    #     v = View(plot,
    #              resizable=self.resizable,
    #              title=self.window_title,
    #              width=self.window_width,
    #              height=self.window_height,
    #              x=self.window_x,
    #              y=self.window_y,
    #              handler=self.handler_klass)
    #
    #     if self.view_identifier:
    #         v.id = self.view_identifier
    #     return v

    # ============= EOF ====================================
    #     def _export_raw_data(self, path, header, plotid):
    #         def name_generator(base):
    #             i = 0
    #             while 1:
    #                 yield '%s%s%8s' % (base, i, '')
    #                 i += 1
    #
    #         xname_gen = name_generator('x')
    #         yname_gen = name_generator('y')
    #
    #         writer = csv.writer(open(path, 'w'))
    #         if plotid is None:
    #             plotid = self.selected_plotid
    #
    # #         xs = self.raw_x[plotid]
    # #         ys = self.raw_y[plotid]
    #
    #         cols = []
    #         nnames = []
    #         for xd, yd in zip(xs, ys):
    #             cols.append(fmt(xd))
    #             cols.append(fmt(yd))
    #             nnames.append(xname_gen.next())
    #             nnames.append(yname_gen.next())
    #
    #         if header is None:
    #             header = nnames
    #         writer.writerow(header)
    #         rows = zip(*cols)
    #         writer.writerows(rows)
    # def _assemble_plot_metadata(self, plot):
    #     meta = dict()
    #     pmeta = dict()
    #     if isinstance(plot, ScatterPlot):
    #         attrs = ['color', 'marker_size', 'marker']
    #     else:
    #         attrs = ['color', 'line_width', 'line_style']
    #
    #     for ai in attrs:
    #         v = getattr(plot, ai)
    #         #            if ai == 'color':
    #         #                print ai, v, type(v)
    #         #                if isinstance(v, str):
    #         #                    v = color_table[v]
    #         #                else:
    #         #                    v=map(lambda x:x*255, v)
    #
    #         meta[ai] = v
    #
    #     meta['plot'] = pmeta
    #
    #     return meta
    #
    # def _assemble_value_axis_metadata(self, v):
    #     vmeta = dict()
    #     vattrs = ['title_spacing', 'tick_visible', 'tick_label_formatter']
    #
    #     for ai in vattrs:
    #         vmeta[ai] = getattr(v, ai)
    #     return vmeta
    #
    # def dump_metadata(self):
    #     ps = []
    #
    #     for p in self.plots:
    #         d = dict()
    #         d['value_axis'] = self._assemble_value_axis_metadata(p.value_axis)
    #         d['xlimits'] = p.index_range.low, p.index_range.high
    #         for k, pp in p.plots.iteritems():
    #             pp = pp[0]
    #             d[k] = self._assemble_plot_metadata(pp)
    #
    #         ps.append(d)
    #
    #     return ps
    #
    # def load_metadata(self, metas):
    #     return
    #
    #     self.debug('loading metadata')
    #
    #     for i, meta in enumerate(metas):
    #         #print meta.keys()
    #         if not meta:
    #             continue
    #         try:
    #             plot = self.plots[i]
    #         except IndexError:
    #             continue
    #
    #         plots = plot.plots
    #         for k, d in meta.iteritems():
    #             obj = None
    #             if k == 'value_axis':
    #                 obj = plot.value_axis
    #             elif k in plots:
    #                 obj = plots[k][0]
    #
    #             if obj:
    #                 for ki, di in d.iteritems():
    #                     if 'color' in ki:
    #                         d[ki] = map(lambda x: x * 255, d[ki])
    #                 obj.trait_set(**d)
    #
    #         mi_, ma_ = meta['xlimits']
    #         self.set_x_limits(min_=mi_, max_=ma_, plotid=i)
    #
    #     self.redraw()
