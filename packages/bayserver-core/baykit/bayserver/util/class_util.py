class ClassUtil:
    @classmethod
    def get_local_name(cls, clazz):
        name = clazz.__name__
        p = name.rfind(':')
        if p >= 0:
            name = name[p + 1:]
        return name