import os
import traceback

from bayserver_core.bay_log import BayLog
from bayserver_core.util.string_util import StringUtil


class Locale:
    def __init__(self, language, country):
        self.language = language
        self.country = country


    @classmethod
    def default(cls):
        lang = os.getenv('LANG')
        if StringUtil.is_set(lang):
            try:
                language = lang[0:2]
                country = lang[3:5]
                return Locale(language, country)

            except BaseException as e:
                BayLog.error_e(e, traceback.format_stack())

        return Locale("en", "US")
