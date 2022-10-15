#
# Ajp packet type
#

class AjpType:
    DATA = 0
    FORWARD_REQUEST = 2
    SEND_BODY_CHUNK = 3
    SEND_HEADERS = 4
    END_RESPONSE = 5
    GET_BODY_CHUNK = 6
    SHUTDOWN = 7
    PING = 8
    CPING = 10