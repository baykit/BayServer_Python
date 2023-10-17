class URLEncoder:
    TILDE_STRING = "~"
    ENCODED_TILDE_STRING = "%7E"

    @classmethod
    def encode_tilde(cls, url):
        return url.replace(cls.TILDE_STRING, cls.ENCODED_TILDE_STRING)