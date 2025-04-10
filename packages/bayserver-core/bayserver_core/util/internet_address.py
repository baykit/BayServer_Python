from typing import Union, Tuple

InternetAddress = Union[
    Tuple[str, int],           # IPv4
    Tuple[str, int, int, int], # IPv6
    str,                       # UNIXドメインソケット
    bytes                      # 一部の特殊ソケット
]
