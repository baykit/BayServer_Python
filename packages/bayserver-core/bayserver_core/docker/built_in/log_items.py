import datetime

from bayserver_core.docker.built_in.log_item import LogItem

class LogItems:
    #
    # Return static text
    #
    class TextItem(LogItem):
        def __init__(self, text):
            self.text = text

        def get_item(self, tour):
            return self.text

    #
    # Return null result
    #
    class NullItem(LogItem):

        def get_item(self, tur):
            return None

    #
    # Return remote IP address (%a)
    #
    class RemoteIpItem(LogItem):

        def get_item(self, tur):
            return tur.req.remote_address

    #
    # Return local IP address (%A)
    #
    class ServerIpItem(LogItem):
        def get_item(self, tur):
            return tur.sever_address

    #
    # Return number of bytes that is sent from clients (Except HTTP headers)
    # (%B)
    #
    class RequestBytesItem1(LogItem):
        def get_item(self, tur):
            length = tur.req.headers.content_length()
            if length < 0:
                length = 0
            return str(length)

    #
    # Return number of bytes that is sent from clients in CLF format (Except
    # HTTP headers) (%b)
    #
    class RequestBytesItem2(LogItem):
        def get_item(self, tur):
            length = tur.req.headers.content_length()
            if length <= 0:
                return "-"
            else:
                return str(length)

    #
    # Return connection status (%c)
    #
    class ConnectionStatusItem(LogItem):
        def get_item(self, tur):
            if tur.is_aborted():
                return "X"
            else:
                return "-"

    #
    # Return file name (%f)
    #
    class FileNameItem(LogItem):
        def get_item(self, tur):
            return tur.req.script_name

    #
    # Return remote host name (%H)
    #
    class RemoteHostItem(LogItem):
        def get_item(self, tur):
            return tur.req.remote_host()

    #
    # Return remote log name (%l)
    #
    class RemoteLogItem(LogItem):
        def get_item(self, tur):
            return None

    #
    # Return request protocol (%m)
    #
    class ProtocolItem(LogItem):
        def get_item(self, tur):
            return tur.req.protocol

    #
    # Return requested header (%{Foobar}i)
    #
    class RequestHeaderItem(LogItem):
        def __init__(self):
            self.name = None

        def init(self, param):
            if param is None:
                param = ""
            self.name = param

        def get_item(self, tur):
            return tur.req.headers.get(self.name)

    #
    # Return request method (%m)
    #
    class MethodItem(LogItem):
        def get_item(self, tur):
            return tur.req.method

    #
    # Return responde header (%{Foobar}o)
    #
    class ResponseHeaderItem(LogItem):
        # Header name
        def __init__(self):
            self.name = None

        def init(self, param):
            if param is None:
                param = ""

            self.name = param

        def get_item(self, tur):
            return tur.res.headers.get(self.name)

    #
    # The server port (%p)
    #
    class PortItem(LogItem):
        def get_item(self, tur):
            return tur.req.server_port

    #
    # Return query string (%q)
    #
    class QueryStringItem(LogItem):
        def get_item(self, tur):
            qStr = tur.query_string
            if qStr:
                return '?' + qStr
            else:
                return ""

    #
    # The start line (%r)
    #
    class StartLineItem(LogItem):
        def get_item(self, tur):
            return f"{tur.req.method} {tur.req.uri} {tur.req.protocol}"

    #
    # Return status (%s)
    #
    class StatusItem(LogItem):
        def get_item(self, tur):
            return tur.res.headers.status

    #
    #  Return current time (%{format}t)
    #
    class TimeItem(LogItem):

        def __init__(self):
            self.format = None

        def init(self, param):
            if not param:
                self.format = "[%d/%m/%Y %H:%M:%S %Z]"
            else:
                self.format = param

        def get_item(self, tur):
            return datetime.datetime.now().strftime(self.format)

    #
    # Return how long request took (%T)
    #
    class IntervalItem(LogItem):
        def get_item(self, tur):
            return (tur.interval / 1000).to_s

    #
    # Return remote user (%u)
    #
    class RemoteUserItem(LogItem):
        def get_item(self, tur):
            return tur.req.remote_user

    #
    # Return requested URL(not content query string) (%U)
    #
    class RequestUrlItem(LogItem):
        def get_item(self, tur):
            url = "" if tur.req.uri is None else tur.req.uri
            pos = url.find('?')
            if pos >= 0:
                url = url[0: pos]
            return url

    #
    # Return the server name (%v)
    #
    class ServerNameItem(LogItem):
        def get_item(self, tur):
            return tur.req.server_name
