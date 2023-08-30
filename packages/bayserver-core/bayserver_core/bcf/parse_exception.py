from bayserver_core.config_exception import ConfigException

class ParseException(ConfigException):
    def __init__(self, file_name, line_no, msg):
        super().__init__(file_name, line_no, msg)