import hashlib

class MD5Password:

    @classmethod
    def encode(cls, password):
        return hashlib.md5(password.encode('utf-8')).hexdigest()
