# ===============================================================================
# Copyright 2018 ross
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

from pychron.processing.analyses.analysis_group import InterpretedAgeGroup


def set_subgrouping_error(tag, selected, items):
    ss = []
    for s in selected:
        if s.subgroup:
            s.subgroup['error_kind'] = tag
            ss.append(s.subgroup['name'])

    if ss:
        # ensure all items in the subgroup get updated
        for i in items:
            if i.subgroup and i.subgroup['name'] in ss:
                i.subgroup['error_kind'] = tag


def apply_subgrouping(sg, selected, items=None, gid=None):
    if len(selected) == 1:
        return

    if items is None and gid is None:
        raise ValueError('must set items or gid')

    if items:
        gs = {r.subgroup['name'] for r in items}
        gs = [int(gi) for gi in gs if gi]
        gid = max(gs) + 1 if gs else 0

    # sha = hashlib.sha1()
    # for s in selected:
    #     sha.update(s.uuid.encode('utf-8'))
    #
    # sha_id = sha.hexdigest()
    # sg = {'name':'{}:{}_{}'.format(sha_id, tag, gid),'error_kind': }
    # sg = {'name': '{:02n}'.format(gid), 'kind': kind, 'error_kind': error_kind, 'sha_id': sha_id}
    sg['name'] = '{:02n}'.format(gid)

    for s in selected:
        s.subgroup = sg

    if items:
        compress_groups(items)


def compress_groups(items):
    def key(x):
        return x.subgroup['name'] if x.subgroup else ''

    cnt = 0
    for kind, ans in groupby(items, key=key):
        if kind:
            ans = list(ans)
            valid_ais = [a for a in ans if not a.is_omitted()]
            if len(valid_ais) > 1:
                v = '{:02n}'.format(cnt)
                for a in ans:
                    a.subgroup['name'] = v
                cnt += 1

            else:
                for a in ans:
                    a.subgroup = None
        else:
            for a in ans:
                a.subgroup = None


def subgrouping_key(x):
    return x.subgroup['name'] if x.subgroup else ''


def make_interpreted_age_subgroups(ans):
    ias = []

    for subgroup, items in groupby(ans, key=subgrouping_key):
        items = list(items)
        if subgroup:
            item = items[0]
            sg = item.subgroup

            items = list(items)
            ag = InterpretedAgeGroup(analyses=items)
            ag.set_preferred_kinds(sg)

            # print('asdf', subgroup, naliquots)
            # for attr in SUBGROUPING_ATTRS:
            #     k = sg.get('{}_kind'.format(attr))
            #     ek = sg.get('{}_error_kind'.format(attr))
            #     if k is None:
            #         if attr == 'age':
            #             k = WEIGHTED_MEAN
            #         else:
            #             k = WEIGHTED_MEAN if naliquots > 1 else INTEGRATED
            #     if ek is None:
            #         if attr == 'age':
            #             ek = MSEM
            #         else:
            #             ek = MSEM if naliquots > 1 else SD
            #     ag.set_preferred_kind(attr, k, ek)

            kind = ag.get_preferred_kind('age')
            ag.label_name = '{:02n}{}'.format(ag.aliquot, kind[:2])
            ag.record_id = '{:02n}{}'.format(ag.aliquot, kind[:2])
            ias.append(ag)
        else:
            ias.extend(items)

    return ias

# ============= EOF =============================================
