import copy


class Cities:
    def __init__(self):
        self.any_city = None
        self.cities = []

    def add(self, c):
        if c.name == "*":
            self.any_city = c
        else:
            self.cities.append(c)

    def find_city(self, name):
        # Check exact match
        for c in self.cities:
            if c.name == name:
                return c

        return self.any_city

    def cities(self):
        ret = copy.copy(self.cities())
        if self.any_city:
            ret += self.any_city
        return ret
