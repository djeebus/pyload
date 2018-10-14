# -*- coding: utf-8 -*-

from pyload.plugins.internal.deadcrypter import DeadCrypter


class MegauploadComFolder(DeadCrypter):
    __name__ = "MegauploadComFolder"
    __type__ = "crypter"
    __version__ = "0.08"
    __pyload_version__ = "0.5"
    __status__ = "stable"

    __pattern__ = (
        r"http://(?:www\.)?megaupload\.com/(\?f|xml/folderfiles\.php\?.*&?folderid)=\w+"
    )
    __config__ = [("activated", "bool", "Activated", True)]

    __description__ = """Megaupload.com folder decrypter plugin"""
    __license__ = "GPLv3"
    __authors__ = [("zoidberg", "zoidberg@mujmail.cz")]
