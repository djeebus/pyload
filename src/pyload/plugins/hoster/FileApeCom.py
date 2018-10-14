# -*- coding: utf-8 -*-

from pyload.plugins.internal.deadhoster import DeadHoster


class FileApeCom(DeadHoster):
    __name__ = "FileApeCom"
    __type__ = "hoster"
    __version__ = "0.17"
    __pyload_version__ = "0.5"
    __status__ = "stable"

    __pattern__ = (
        r"http://(?:www\.)?fileape\.com/(index\.php\?act=download\&id=|dl/)\w+"
    )
    __config__ = []  # TODO: Remove in 0.6.x

    __description__ = """FileApe.com hoster plugin"""
    __license__ = "GPLv3"
    __authors__ = [("espes", None)]
