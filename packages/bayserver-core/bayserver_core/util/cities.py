import copy
from typing import List

from bayserver_core.docker.city import City


class Cities:

    _any_city: City
    _cities: List[City]

    def __init__(self):
        self._any_city = None
        self._cities = []

    def add(self, c):
        if c.name == "*":
            self._any_city = c
        else:
            self._cities.append(c)

    def find_city(self, name):
        # Check exact match
        for c in self._cities:
            if c.name == name:
                return c

        return self._any_city

    def cities(self) -> List[City]:
        ret = copy.copy(self._cities)
        if self._any_city:
            ret.append(self._any_city)
        return ret
