# ===============================================================================
# Copyright 2012 Jake Ross
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

# ============= standard library imports ========================
from __future__ import absolute_import
from __future__ import print_function

from copy import copy
from operator import itemgetter

from uncertainties import ufloat, std_dev, nominal_value

from pychron.core.helpers.isotope_utils import sort_detectors
from pychron.processing.arar_constants import ArArConstants
from pychron.processing.argon_calculations import calculate_F, abundance_sensitivity_correction, age_equation, \
    calculate_decay_factor, calculate_flux
from pychron.processing.isotope import Blank
from pychron.processing.isotope_group import IsotopeGroup
from pychron.pychron_constants import ARGON_KEYS


class ArArAge(IsotopeGroup):
    """
    High level representation of the ArAr attributes of an analysis.
    """

    j = None
    irradiation = None
    irradiation_level = None
    irradiation_position = None
    irradiation_time = 0
    production_name = None

    chron_segments = None
    chron_dosages = None
    # interference_corrections = Dict
    # production_ratios = Dict

    fixed_k3739 = None

    timestamp = None

    kca = 0
    cak = 0
    kcl = 0
    clk = 0
    rad40_percent = 0
    rad40 = 0
    total40 = 0
    k39 = 0


    # non_ar_isotopes = Dict
    # computed = Dict
    # corrected_intensities = Dict

    uF = None
    F = None
    F_err = None
    F_err_wo_irrad = None

    uage = None
    # uage_wo_j_err =None
    uage_w_j_err = None
    uage_wo_j_err = None

    age = 0
    age_err = 0
    age_err_wo_j = 0
    age_err_wo_irrad = 0
    age_err_wo_j_irrad = 0

    ar39decayfactor = 0
    ar37decayfactor = 0

    # arar_constants =None

    Ar39_decay_corrected = None
    Ar37_decay_corrected = None

    sensitivity = 1e-17  # fA/torr
    sensitivity_units = 'mol/fA'

    # temporary_ic_factors =None

    _missing_isotope_warned = False
    _kca_warning = False
    _kcl_warning = False
    _lambda_k = None

    discrimination = None
    weight = 0  # in milligrams
    rundate = None

    def __init__(self, *args, **kw):
        super(ArArAge, self).__init__(*args, **kw)
        self.arar_constants = ArArConstants()
        self.isotopes = {}
        self.non_ar_isotopes = {}
        self.computed = {}
        self.corrected_intensities = {}
        self.interference_corrections = {}
        self.production_ratios = {}
        self.temporary_ic_factors = {}
        self.discrimination = ufloat(1, 0)

    @property
    def k2o(self):
        """
            MolKTot=Mol39*F39K*9.54/(JVal*KAbund40*.01) // moles of K40; = 39ArK*( (lambda*J/(lambda epsilon + lambda epsion prime)); McDougall  H. p. 19 eq. 2.17
            a=MolKTot*94.2*100/(2*Weight)

        weight should be in milligrams
        @return:
        """
        k2o = ''
        if self.weight:
            k40_k = 0.0001167
            k40 = self.non_ar_isotopes['k40']
            moles_k = k40 / k40_k * self.sensitivity
            mw_k2o = 94.2
            k2o = (moles_k * mw_k2o * 100) / (2 * self.weight * 0.001)
        return k2o

    @property
    def isochron3940(self):
        a = self.get_interference_corrected_value('Ar39')
        b = self.get_interference_corrected_value('Ar40')
        return a / b

    @property
    def isochron3640(self):
        a = self.get_interference_corrected_value('Ar36')
        b = self.get_interference_corrected_value('Ar40')
        return a / b

    @property
    def lambda_k(self):
        l = self._lambda_k
        if l is None:
            l = self.arar_constants.lambda_k
        return l

    @lambda_k.setter
    def lambda_k(self, v):
        self._lambda_k = v

    def get_error_component(self, key):
        # for var, error in self.uage.error_components().items():
        #     print var.tag
        uage = self.uage_w_j_err
        ae = 0
        if uage:
            # for var, err in uage.error_components().items():
            #     if var.tag == key:
            #         # print('var', key, var.tag, var)
            #         break
            # else:
            #     print('tags', [var.tag for (var,error) in  uage.error_components().items()])
            #     print('not found', key)

            v = next((error for (var, error) in uage.error_components().items()
                      if var.tag == key), 0)

            ae = uage.std_dev
            # print(key, v)
        if ae:
            return v ** 2 / ae ** 2 * 100
        else:
            return 0

    def set_sensitivity(self, sens):
        # for si in sens:
        #     si['create_date'] = datetime.strptime(si['create_date'], DATE_FORMAT)

        for si in sorted(sens, key=itemgetter('create_date'), reverse=True):
            if si['create_date'] < self.rundate:
                self.sensitivity = si['sensitivity']
                self.sensitivity_units = si['units']
                break

    def set_temporary_ic_factor(self, k, v, e, tag=None):
        self.temporary_ic_factors[k] = uv = ufloat(v, e, tag=tag)
        return uv

    def set_temporary_blank(self, k, v, e, f):
        tol = 0.00001
        if k in self.isotopes:
            iso = self.isotopes[k]
            if iso.temporary_blank is not None:
                tb = iso.temporary_blank
                if abs(tb.value - v) < tol and abs(tb.error - e) < tol:
                    return
                else:
                    self.debug('temp blank {}({:0.4f}+/-{:0.4f}) fit={}'.format(k, v, e, f))
                    tb.value, tb.error, tb.fit = v, e, f
            else:
                self.debug('temp blank {}({:0.4f}+/-{:0.4f}) fit={}'.format(k, v, e, f))
                iso.temporary_blank = b = Blank(k, iso.detector)
                b.value = v
                b.error = e
                b.fit = f

    def set_j(self, s, e):
        self.j = ufloat(s, std_dev=e, tag='J')

    def get_corrected_ratio(self, n, d):
        isos = self.isotopes
        if n in isos and d in isos:
            try:
                nn = isos[n].get_interference_corrected_value()
                dd = isos[d].get_interference_corrected_value()
                return nn / dd
            except ZeroDivisionError:
                pass

    def get_value(self, attr):
        r = ufloat(0, 0, tag=attr)
        if attr.endswith('bs'):
            iso = attr[:-2]
            if iso in self.isotopes:
                r = self.isotopes[iso].baseline.uvalue
        elif attr in ('uage_wo_j_err', 'uage_w_j_err', 'uF'):
            r = getattr(self, attr)
        elif attr.startswith('u') and ('/' in attr or '_' in attr):
            attr = attr[1:]
            r = self.get_ratio(attr, non_ic_corr=True)
        elif attr == 'icf_40_36':
            r = self.get_corrected_ratio('Ar40', 'Ar36')
        elif attr.endswith('ic'):
            # ex. attr='Ar40ic'
            isok = attr[:-2]
            try:
                r = self.isotopes[isok].ic_factor
            except KeyError:
                r = ufloat(0, 0)
        elif attr.endswith('DetIC'):
            r = ufloat(0, 0)
            ratio = attr.split(' ')[0]
            numkey, denkey = ratio.split('/')
            num, den = None, None
            for iso in self.isotopes.values():
                if iso.detector == numkey:
                    num = iso.get_non_detector_corrected_value()
                elif iso.detector == denkey:
                    den = iso.get_non_detector_corrected_value()
            if num and den:
                r = num / den

        elif attr in self.computed:
            r = self.computed[attr]
        elif attr in self.isotopes:
            r = self.isotopes[attr].get_intensity()
        else:
            if hasattr(self, attr):
                r = getattr(self, attr)

        return r

    def get_interference_corrected_value(self, iso):
        if iso in self.isotopes:
            return self.isotopes[iso].get_interference_corrected_value()
        else:
            return ufloat(0, 0, tag=iso)

    def calculate_F(self):
        self.calculate_decay_factors()
        self._calculate_F()

    # @caller

    def model_j(self, monitor_age, lambda_k):
        j = calculate_flux(self.uF, monitor_age, lambda_k=lambda_k)
        return j

    def recalculate_age(self):
        print('recacl age', self)
        if not self.uF:
            self._calculate_F()

        self._set_age_values(self.uF)

    def calculate_age(self, use_display_age=False, force=False, **kw):
        """
            force: force recalculation of age. necessary if you want error components
        """

        if not self.age or force:
            self.calculate_decay_factors()

            self._calculate_age(use_display_age=use_display_age, **kw)
            self._calculate_kca()
            self._calculate_kcl()

    def calculate_decay_factors(self):
        arc = self.arar_constants
        # only calculate decayfactors once
        if not self.ar39decayfactor:
            a37df = calculate_decay_factor(nominal_value(arc.lambda_Ar37),
                                           self.chron_segments)
            a39df = calculate_decay_factor(nominal_value(arc.lambda_Ar39),
                                           self.chron_segments)
            # print a37df, a39df, self.chron_segments, self.chron_dosages
            self.ar37decayfactor = a37df
            self.ar39decayfactor = a39df

    def get_non_ar_isotope(self, key):
        return self.non_ar_isotopes.get(key, ufloat(0, 0))

    def get_computed_value(self, key):
        return self.computed.get(key, ufloat(0, 0))

    # private
    def _calculate_kca(self):
        # self.debug('calculated kca')

        k = self.get_computed_value('k39')
        ca = self.get_non_ar_isotope('ca37')
        prs = self.production_ratios
        k_ca_pr = 1
        if prs:
            cak = prs.get('Ca_K', 1)
            if not cak:
                cak = 1.0

            k_ca_pr = 1 / cak

        try:
            self.kca = k / ca * k_ca_pr
        except ZeroDivisionError:
            self.kca = ufloat(0, 0)
            if not self._kca_warning:
                self._kca_warning = True
                self.debug("ca37 is zero. can't calculated k/ca")

    def _calculate_kcl(self):
        k = self.get_computed_value('k39')
        cl = self.get_non_ar_isotope('cl38')

        prs = self.production_ratios
        k_cl_pr = 1
        if prs:
            clk = prs.get('Cl_K', 1)
            if not clk:
                clk = 1.0

            k_cl_pr = 1 / clk
        try:
            self.kcl = k / cl * k_cl_pr
        except ZeroDivisionError:
            self.kcl = ufloat(0, 0)
            if not self._kcl_warning:
                self._kcl_warning = True
                self.warning("cl38 is zero. can't calculated k/cl")

    def _assemble_ar_ar_isotopes(self):
        isotopes = self.isotopes
        for ik in ARGON_KEYS:
            try:
                isotopes[ik]
            except KeyError:
                if not self._missing_isotope_warned:
                    self.warning('No isotope= "{}". Required for age calculation'.format(ik))
                self._missing_isotope_warned = True
                return
        else:
            self._missing_isotope_warned = False

        return [isotopes[ik].get_intensity() for ik in ARGON_KEYS]

    def _calculate_F(self, iso_intensities=None, interferences=None):

        if iso_intensities is None:
            iso_intensities = self._assemble_isotope_intensities()

        if iso_intensities:
            if interferences is None:
                interferences = self.interference_corrections

            f, f_wo_irrad, non_ar, computed, interference_corrected = calculate_F(iso_intensities,
                                                                                  decay_time=self.decay_days,
                                                                                  interferences=interferences,
                                                                                  arar_constants=self.arar_constants,
                                                                                  fixed_k3739=self.fixed_k3739)

            self.uF = f
            self.F = nominal_value(f)
            self.F_err = std_dev(std_dev)
            self.F_err_wo_irrad = std_dev(f_wo_irrad)
            return f, f_wo_irrad, non_ar, computed, interference_corrected

    def _assemble_isotope_intensities(self):
        iso_intensities = self._assemble_ar_ar_isotopes()
        if not iso_intensities:
            self.debug('failed assembling isotopes')
            return

        arc = self.arar_constants
        iso_intensities = abundance_sensitivity_correction(iso_intensities, arc.abundance_sensitivity)

        # assuming all m/z(39) and m/z(37) is radioactive argon
        # non gettered hydrocarbons will have a multiplicative systematic influence
        iso_intensities[1] *= self.ar39decayfactor
        iso_intensities[3] *= self.ar37decayfactor
        return iso_intensities

    def calculate_no_interference(self):
        self._calculate_age(interferences={})

    def _calculate_age(self, use_display_age=False, include_decay_error=None, interferences=None):
        """
            approx 2/3 of the calculation time is in _assemble_ar_ar_isotopes.
            Isotope.get_intensity takes about 5ms.
        """
        # self.debug('calculate age')
        iso_intensities = self._assemble_isotope_intensities()
        if not iso_intensities:
            return

        self.Ar39_decay_corrected = iso_intensities[1]
        self.Ar37_decay_corrected = iso_intensities[3]

        self.isotopes['Ar37'].decay_corrected = self.Ar37_decay_corrected
        self.isotopes['Ar39'].decay_corrected = self.Ar39_decay_corrected

        # self.debug('allow_negative ca correction {}'.format(arc.allow_negative_ca_correction))
        self.corrected_intensities = dict(Ar40=iso_intensities[0],
                                          Ar39=iso_intensities[1],
                                          Ar38=iso_intensities[2],
                                          Ar37=iso_intensities[3],
                                          Ar36=iso_intensities[4])

        f, f_wo_irrad, non_ar, computed, interference_corrected = self._calculate_F(iso_intensities,
                                                                                    interferences=interferences)

        self.non_ar_isotopes = non_ar
        self.computed = computed
        self.rad40_percent = computed['rad40_percent']
        self.rad40 = computed['rad40']
        self.total40 = computed['a40']
        self.k39 = computed['k39']

        isotopes = self.isotopes
        for k, v in interference_corrected.items():
            isotopes[k].interference_corrected_value = v

        self._set_age_values(f, include_decay_error)

    def _set_age_values(self, f, include_decay_error=False):
        if self.j is not None:
            j = copy(self.j)
        else:
            j = ufloat(1e-4, 1e-7)

        arc = self.arar_constants
        age = age_equation(j, f, include_decay_error=include_decay_error,
                           # lambda_k=self.lambda_k,
                           arar_constants=arc)
        # age = ufloat((1, 0.1))
        self.uage_w_j_err = age
        # self.age = age.nominal_value
        # self.age_err = age.std_dev

        if self.j is not None:
            j = copy(self.j)
        else:
            j = ufloat(1e-4, 1e-7)

        j.std_dev = 0
        age = age_equation(j, f, include_decay_error=include_decay_error,
                           # lambda_k=self.lambda_k,
                           arar_constants=arc)
        self.uage = age

        self.age = nominal_value(age)
        self.age_err = std_dev(age)
        self.age_err_wo_j = std_dev(age)

        # self.uage = ufloat(self.age, self.age_err)
        self.uage_wo_j_err = ufloat(self.age, self.age_err_wo_j)

        # if self.j is not None:
        # j = copy(self.j)
        # else:
        # j = ufloat(1e-4, 1e-7)
        #
        # age = age_equation(j, f_wo_irrad, include_decay_error=include_decay_error,
        #                    arar_constants=arc)
        #
        # self.age_err_wo_irrad = age.std_dev
        # j.std_dev = 0
        # self.age_err_wo_j_irrad = age.std_dev
        #
        for iso in self.itervalues():
            iso.age_error_component = self.get_error_component(iso.name)

    # def _get_isotope_keys(self):
    #     keys = self.isotopes.keys()
    #     return sort_isotopes(keys)
    #
    # def _get_irradiation_label(self):
    #     return '{}{} {}'.format(self.irradiation,
    #                             self.irradiation_level,
    #                             self.irradiation_pos)
    #
    # def _get_decay_days(self):
    #     """
    #         return number of days since irradiation
    #     """
    #     return (self.timestamp - self.irradiation_time) / (60 * 60 * 24)
    #
    # @cached_property
    # def _get_moles_Ar40(self):
    #     return self.sensitivity * self.get_isotope('Ar40').get_intensity()

    @property
    def detector_keys(self):
        return sort_detectors(set((d.detector for d in self.isotopes.values())))

    # @property
    # def isotope_keys(self):
    #     keys = self.isotopes.keys()
    #     return sort_isotopes(keys)

    @property
    def irradiation_label(self):
        return '{}{} {}'.format(self.irradiation,
                                self.irradiation_level,
                                self.irradiation_position)

    @property
    def decay_days(self):
        """
            return number of days since irradiation
        """
        return (self.timestamp - self.irradiation_time) / (60 * 60 * 24)

    @property
    def moles_k39(self):
        return self.sensitivity * self.k39

    @property
    def signal_k39(self):
        return self.k39

    @property
    def moles_Ar40(self):
        return self.sensitivity * self.get_isotope('Ar40').get_intensity()

        # def __getattr__(self, attr):
        #     if '/' in attr:
        #         # treat as ratio
        #         n, d = attr.split('/')
        #         try:
        #             return self.get_value(n) / self.get_value(d)
        #         except (ZeroDivisionError, TypeError):
        #             return ufloat(0, 1e-20)
        #     else:
        #         raise AttributeError(attr)
        # ===============================================================================
        #
        # ===============================================================================

        # def _arar_constants_default(self):
        #     """
        #         use a global shared arar_constants
        #     """
        #
        #     global arar_constants
        #     #self.debug('$$$$$$$$$$$$$$$$ {}'.format(arar_constants))
        #     #print 'asdf', arar_constants
        #     if arar_constants is None:
        #         arar_constants = ArArConstants()
        #         #return ArArConstants()
        #     return arar_constants

        # def _arar_constants_default(self):
        #     """
        #         use a global shared arar_constants
        #     """
        #
        #     global arar_constants
        #     #self.debug('$$$$$$$$$$$$$$$$ {}'.format(arar_constants))
        #     #print 'asdf', arar_constants
        #     if arar_constants is None:
        #         arar_constants = ArArConstants()
        #         #return ArArConstants()
        #     return arar_constants

        # ============= EOF =============================================
