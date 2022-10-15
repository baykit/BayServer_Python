class URLEncoder:
    ENCODED_TILDE_BYTES = "%7E".encode("us-ascii")

    @classmethod
    def encode_tilde(cls, url):
        if url.find("~") == -1:
            return url

        buf = bytearray()
        for c in url:
            if c == "~":
                buf.append(cls.ENCODED_TILDE_BYTES)
            else:
                buf.append(ord(c))

        return buf.decode("us-ascii")