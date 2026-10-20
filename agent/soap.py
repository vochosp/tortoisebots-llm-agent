"""Sends server console commands over the mangosd SOAP interface."""

import base64
import re
import time
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

ENVELOPE = """<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="urn:MaNGOS">
<SOAP-ENV:Body><ns1:executeCommand><command>{}</command></ns1:executeCommand></SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""


class Soap:
    def __init__(self, url, user, password):
        self.url = url
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        self.auth = "Basic " + token

    def run(self, command):
        """Returns (ok, result text, milliseconds)."""
        request = urllib.request.Request(
            self.url,
            data=ENVELOPE.format(escape(command)).encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8", "Authorization": self.auth},
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                text, ok = response.read().decode("utf-8", "replace"), True
        except urllib.error.HTTPError as error:
            # A failed command comes back as HTTP 500 with a SOAP fault.
            text, ok = error.read().decode("utf-8", "replace"), False
        ms = round((time.perf_counter() - start) * 1000)
        match = re.search(r"<result>(.*?)</result>|<faultstring>(.*?)</faultstring>", text, re.S)
        if match:
            text = (match.group(1) or match.group(2) or "").strip()
        return ok, text, ms
