import sys

from bayserver_core import bay_message as msg
from bayserver_core.symbol import Symbol

from bayserver_core.bcf.bcf_document import BcfDocument
from bayserver_core.bcf.bcf_element import BcfElement
from bayserver_core.bcf.bcf_key_val import BcfKeyVal
from bayserver_core.bcf.parse_exception import ParseException

class BcfParser:
    class LineInfo:
        def __init__(self, line_obj, indent):
            if indent is None:
                raise Exception("indent is None")

            self.line_obj = line_obj
            self.indent = indent

    def __init__(self):
        self.file_name = None
        self.line_no = None
        self.input = None
        self.prev_line_info = None
        self.indent_map = []

    def parse(self, file):
        doc = BcfDocument()
        self.file_name = file
        self.line_no = 0

        enc = sys.getdefaultencoding()
        if enc is None:
            enc = "utf-8"
        self.input = open(file, encoding=enc)
        self.parse_same_level(doc.content_list, 0)
        self.input.close()
        return doc

    def push_indent(self, sp_count):
        self.indent_map.append(sp_count)

    def pop_indent(self):
        return self.indent_map.pop(len(self.indent_map) - 1)

    def get_indent(self, sp_count):
        if len(self.indent_map) == 0:
            self.push_indent(sp_count)
        elif sp_count > self.indent_map[len(self.indent_map) - 1]:
            self.push_indent(sp_count)

        try:
            indent = self.indent_map.index(sp_count)
        except ValueError:
            raise ParseException(self.file_name, self.line_no, msg.BayMessage.get(Symbol.PAS_INVALID_INDENT))

        return indent

    def parse_same_level(self, cur_list, indent):
        object_exists_in_same_level = False
        while True:
            if self.prev_line_info is not None:
                line_info = self.prev_line_info
                self.prev_line_info = None
            else:
                line = self.input.readline()
                self.line_no += 1

                if line == "":
                    break

                if line.strip().startswith("#") or line.strip() == "":
                    continue

                line_info = self.parse_line(self.line_no, line)

            if line_info is None:
                # Comment or empty
                continue

            elif line_info.indent > indent:
                # lower level
                raise ParseException(self.file_name, self.line_no, msg.BayMessage.get(Symbol.PAS_INVALID_INDENT))

            elif line_info.indent < indent:
                # upper level
                self.prev_line_info = line_info
                if object_exists_in_same_level:
                    self.pop_indent()

                return line_info

            else:
                object_exists_in_same_level = True

                # samel level
                if isinstance(line_info.line_obj, BcfElement):
                    # BcfElement
                    cur_list.append(line_info.line_obj)

                    last_line_info = self.parse_same_level(line_info.line_obj.content_list, line_info.indent + 1)
                    if last_line_info is None:
                        # EOF
                        self.pop_indent()
                        return None
                    else:
                        # Same level
                        continue
                else:
                    # IniKeyVal
                    cur_list.append(line_info.line_obj)

        self.pop_indent()
        return None

    def parse_line(self, line_no, line):
        sp_count = 0
        for sp_count in range(len(line)):
            c = line[sp_count]
            if c.strip() != '':
                # c is not awhitespace
                break

            if c != ' ':
              raise ParseException(self.file_name, self.line_no, msg.BayMessage.get(Symbol.PAS_INVALID_WHITESPACE))

        indent = self.get_indent(sp_count)
        line = line[sp_count:]
        line = line.strip()

        if line.startswith("["):
            try:
                close_pos = line.index("]")
            except ValueError:
                raise ParseException(self.file_name, self.line_no, msg.BayMessage.get(Symbol.PAS_BRACE_NOT_CLOSED))

            if not line.endswith("]"):
                raise ParseException(self.file_name, self.line_no, msg.BayMessage.get(Symbol.PAS_INVALID_LINE))

            key_val = self.parse_key_val(line[1:close_pos], line_no)
            return BcfParser.LineInfo(BcfElement(key_val.key, key_val.value, self.file_name, line_no), indent)

        else:
            return BcfParser.LineInfo(self.parse_key_val(line, line_no), indent)

    def parse_key_val(self, line, line_no):
        try:
            sp_pos = line.index(' ')
            key = line[:sp_pos]
            val = line[sp_pos:].strip()
        except ValueError:
            key = line
            val = ""

        return BcfKeyVal(key, val, self.file_name, line_no)
