from typing import List, Optional

from bayserver_core.docker.barge import Barge


class Barges:

    # Default barge docker
    any_barge: Optional[Barge]

    # Barge dockers
    barges: List[Barge]

    def __init__(self):
        self.any_barge = None
        self.barges = []

    def add(self, b: Barge) -> None:
        if b.name() == "*":
            self.any_barge = b
        else:
            self.barges.append(b)

    def find_barge(self, path: str) -> Optional[Barge]:
        # Check exact match
        for b in self.barges:
            if self._match(b, path):
                return b

        return self.any_barge

    def _match(self, b: Barge, path: str) -> bool:
        return True
