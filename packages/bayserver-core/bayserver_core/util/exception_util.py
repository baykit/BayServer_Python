class ExceptionUtil:

    @classmethod
    def message(cls, err):
        return str(err.args) if err else ""