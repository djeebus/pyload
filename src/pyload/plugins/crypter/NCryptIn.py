# -*- coding: utf-8 -*-

import binascii
import re
from builtins import _, filter, zip

import Cryptodome.Cipher.AES
import js2py
from pyload.plugins.captcha.ReCaptcha import ReCaptcha
from pyload.plugins.internal.crypter import Crypter


class NCryptIn(Crypter):
    __name__ = "NCryptIn"
    __type__ = "crypter"
    __version__ = "1.43"
    __pyload_version__ = "0.5"
    __status__ = "testing"

    __pattern__ = r"http://(?:www\.)?ncrypt\.in/(?P<TYPE>folder|link|frame)-([^/\?]+)"
    __config__ = [
        ("activated", "bool", "Activated", True),
        ("use_premium", "bool", "Use premium account if available", True),
        (
            "folder_per_package",
            "Default;Yes;No",
            "Create folder for each package",
            "Default",
        ),
    ]

    __description__ = """NCrypt.in decrypter plugin"""
    __license__ = "GPLv3"
    __authors__ = [
        ("fragonib", "fragonib[AT]yahoo[DOT]es"),
        ("stickell", "l.stickell@yahoo.it"),
    ]

    JK_KEY = "jk"
    CRYPTED_KEY = "crypted"

    NAME_PATTERN = r'<meta name="description" content="(?P<N>.+?)"'

    def setup(self):
        self.package = None
        self.cleaned_html = None
        self.links_source_order = ["cnl2", "rsdf", "ccf", "dlc", "web"]
        self.protection_type = None

    def decrypt(self, pyfile):
        #: Init
        self.package = pyfile.package()
        pack_links = []
        pack_name = self.package.name
        folder_name = self.package.folder

        #: Deal with single links
        if self.is_single_link():
            pack_links.extend(self.handle_single_link())

        #: Deal with folders
        else:

            #: Request folder home
            self.data = self.request_folder_home()
            self.cleaned_html = self.remove_html_crap(self.data)
            if not self.is_online():
                self.offline()

            #: Check for folder protection
            if self.is_protected():
                self.data = self.unlock_protection()
                self.cleaned_html = self.remove_html_crap(self.data)
                self.handle_errors()

            #: Prepare package name and folder
            (pack_name, folder_name) = self.get_package_info()

            #: Extract package links
            for link_source_type in self.links_source_order:
                pack_links.extend(self.handle_link_source(link_source_type))
                if pack_links:  #: Use only first source which provides links
                    break
            pack_links = set(pack_links)

        #: Pack and return links
        if pack_links:
            self.packages = [(pack_name, pack_links, folder_name)]

    def is_single_link(self):
        link_type = re.match(self.__pattern__, self.pyfile.url).group("TYPE")
        return link_type in ("link", "frame")

    def request_folder_home(self):
        return self.load(self.pyfile.url)

    def remove_html_crap(self, content):
        patterns = (
            r'(type="hidden".*?(name=".*?")?.*?value=".*?")',
            r'display:none;">(.*?)</(div|span)>',
            r'<div\s+class="jdownloader"(.*?)</div>',
            r'<table class="global">(.*?)</table>',
            r'<iframe\s+style="display:none(.*?)</iframe>',
        )
        for pattern in patterns:
            rexpr = re.compile(pattern, re.S)
            content = re.sub(rexpr, "", content)
        return content

    def is_online(self):
        if "Your folder does not exist" in self.cleaned_html:
            self.log_debug("File not found")
            return False
        return True

    def is_protected(self):
        form = re.search(
            r"<form.*?name.*?protected.*?>(.*?)</form>", self.cleaned_html, re.S
        )
        if form:
            content = form.group(1)
            for keyword in ("password", "captcha"):
                if keyword in content:
                    self.protection_type = keyword
                    self.log_debug(
                        "Links are {} protected".format(self.protection_type)
                    )
                    return True
        return False

    def get_package_info(self):
        m = re.search(self.NAME_PATTERN, self.data)
        if m is not None:
            name = folder = m.group("N").strip()
            self.log_debug(
                "Found name [{}] and folder [{}] in package info".format(name, folder)
            )
        else:
            name = self.package.name
            folder = self.package.folder
            self.log_debug(
                "Package info not found, defaulting to pyfile name [{}] and folder [{}]".format(
                    name, folder
                )
            )
        return name, folder

    def unlock_protection(self):
        postData = {}

        form = re.search(
            r'<form name="protected"(.*?)</form>', self.cleaned_html, re.S
        ).group(1)

        #: Submit package password
        if "password" in form:
            password = self.get_password()
            self.log_debug(
                "Submitting password [{}] for protected links".format(password)
            )
            postData["password"] = password

        #: Resolve anicaptcha
        if "anicaptcha" in form:
            self.log_debug("Captcha protected")
            captchaUri = re.search(r'src="(/temp/anicaptcha/.+?)"', form).group(1)
            captcha = self.captcha.decrypt("http://ncrypt.in" + captchaUri)
            self.log_debug("Captcha resolved [{}]".format(captcha))
            postData["captcha"] = captcha

        #: Resolve recaptcha
        if "recaptcha" in form:
            self.log_debug("ReCaptcha protected")
            captcha_key = re.search(r'\?k=(.*?)"', form).group(1)
            self.log_debug("Resolving ReCaptcha with key [{}]".format(captcha_key))
            self.captcha = ReCaptcha(self.pyfile)
            response, challenge = self.captcha.challenge(captcha_key)
            postData["recaptcha_challenge_field"] = challenge
            postData["recaptcha_response_field"] = response

        #: Resolve circlecaptcha
        if "circlecaptcha" in form:
            self.log_debug("CircleCaptcha protected")
            captcha_img_url = "http://ncrypt.in/classes/captcha/circlecaptcha.php"
            coords = self.captcha.decrypt(
                captcha_img_url,
                input_type="png",
                output_type="positional",
                ocr="CircleCaptcha",
            )
            self.log_debug("Captcha resolved, coords {}".format(coords))
            postData["circle.x"] = coords[0]
            postData["circle.y"] = coords[1]

        #: Unlock protection
        postData["submit_protected"] = "Continue to folder"
        return self.load(self.pyfile.url, post=postData)

    def handle_errors(self):
        if self.protection_type == "password":
            if "This password is invalid!" in self.cleaned_html:
                self.fail(_("Wrong password"))

        if self.protection_type == "captcha":
            if "The securitycheck was wrong" in self.cleaned_html:
                self.retry_captcha()
            else:
                self.captcha.correct()

    def handle_link_source(self, link_source_type):
        #: Check for JS engine
        require_js = link_source_type in ("cnl2", "rsdf", "ccf", "dlc")
        if require_js and not self.js:
            self.log_debug(
                "No JS engine available, skip {} links".format(link_source_type)
            )
            return []

        #: Select suitable handler
        if link_source_type == "single":
            return self.handle_single_link()
        if link_source_type == "cnl2":
            return self.handle_CNL2()
        elif link_source_type in ("rsdf", "ccf", "dlc"):
            return self.handle_container()
        elif link_source_type == "web":
            return self.handle_web_links()
        else:
            self.error(_('Unknown source type "{}"').format(link_source_type))

    def handle_single_link(self):
        self.log_debug("Handling Single link")
        pack_links = []

        #: Decrypt single link
        decrypted_link = self.decrypt_link(self.pyfile.url)
        if decrypted_link:
            pack_links.append(decrypted_link)

        return pack_links

    def handle_CNL2(self):
        self.log_debug("Handling CNL2 links")
        pack_links = []

        if "cnl2_output" in self.cleaned_html:
            try:
                (vcrypted, vjk) = self._get_cipher_params()
                for (crypted, jk) in zip(vcrypted, vjk):
                    pack_links.extend(self._get_links(crypted, jk))

            except Exception:
                self.fail(_("Unable to decrypt CNL2 links"))

        return pack_links

    def handle_container(self):
        self.log_debug("Handling Container links")
        pack_links = []

        pattern = r"/container/(rsdf|dlc|ccf)/(\w+)"
        containersLinks = re.findall(pattern, self.data)
        self.log_debug("Decrypting {} Container links".format(len(containersLinks)))
        for containerLink in containersLinks:
            link = "http://ncrypt.in/container/{}/{}.{}".format(
                containerLink[0], containerLink[1], containerLink[0]
            )
            pack_links.append(link)

        return pack_links

    def handle_web_links(self):
        self.log_debug("Handling Web links")
        pattern = r"(http://ncrypt\.in/link-.*?=)"
        links = re.findall(pattern, self.data)

        pack_links = []
        self.log_debug("Decrypting {} Web links".format(len(links)))
        for i, link in enumerate(links):
            self.log_debug("Decrypting Web link {}, {}".format(i + 1, link))
            decrypted_link = self.decrypt(link)
            if decrypted_link:
                pack_links.append(decrypted_link)

        return pack_links

    def decrypt_link(self, link):
        try:
            url = link.replace("link-", "frame-")
            link = self.load(url, just_header=True)["location"]
            return link

        except Exception as detail:
            self.log_debug("Error decrypting link {}, {}".format(link, detail))

    def _get_cipher_params(self):
        pattern = r'<input.*?name="{}".*?value="(.*?)"'

        #: Get jk
        jk_re = pattern.format(NCryptIn.JK_KEY)
        vjk = re.findall(jk_re, self.data)

        #: Get crypted
        crypted_re = pattern.format(NCryptIn.CRYPTED_KEY)
        vcrypted = re.findall(crypted_re, self.data)

        #: Log and return
        self.log_debug("Detected {} crypted blocks".format(len(vcrypted)))
        return vcrypted, vjk

    def _get_links(self, crypted, jk):
        #: Get key
        jreturn = js2py.eval_js("{} f()".format(jk))
        self.log_debug("JsEngine returns value [{}]".format(jreturn))
        key = binascii.unhexlify(jreturn)

        #: Decrypt
        Key = key
        IV = key
        obj = Cryptodome.Cipher.AES.new(Key, Cryptodome.Cipher.AES.MODE_CBC, IV)
        text = obj.decrypt(crypted.decode("base64"))

        #: Extract links
        text = text.replace("\x00", "").replace("\r", "")
        links = list(filter(bool, text.split("\n")))

        #: Log and return
        self.log_debug("Block has {} links".format(len(links)))
        return links
