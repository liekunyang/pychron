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
import os

from traits.api import HasTraits

# ============= standard library imports ========================
# ============= local library imports  ==========================
from pychron.core.helpers.filetools import add_extension
from pychron.paths import paths


class PipelineTemplate(HasTraits):
    def __init__(self, name, *args, **kw):
        super(PipelineTemplate, self).__init__(*args, **kw)

        path = os.path.join(paths.pipeline_template_dir, add_extension(name, '.yaml'))

# ============= EOF =============================================



