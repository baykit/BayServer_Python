from bayserver_core.util.md5_password import MD5Password
from bayserver_core.bcf.bcf_parser import BcfParser
from bayserver_core.bcf.bcf_element import BcfElement
from bayserver_core.bcf.bcf_key_val import BcfKeyVal

class Groups:

    class Member:
        def __init__(self, name, digest):
            self.name = name
            self.digest = digest

        def validate(self, password):
            if password is None:
              return False

            dig = MD5Password.encode(password)
            return dig == self.digest

    class Group:
        def __init__(self, groups, name):
            self.name = name
            self.groups = groups
            self.members = []

        def add(self, mem):
            self.members.append(mem)

        def validate(self, mem_name, passwd):
            if mem_name not in self.members:
                return False

            m = self.groups.all_members.get(mem_name)
            if m is None:
                return False

            return m.validate(passwd)


    def __init__(self):
        self.all_groups = {}
        self.all_members = {}


    def init(self, group_file):
        p = BcfParser()
        doc = p.parse(group_file)

        for obj in doc.content_list:
            if isinstance(obj, BcfElement):
                name = obj.name.lower()
                if name == "group":
                    self.init_groups(obj)
                elif name == "member":
                    self.init_members(obj)


    def get_group(self, name):
        return self.all_groups.get(name)

    #################################################################
    # Private
    #################################################################

    def init_groups(self, elm):
        for obj in elm.content_list:
            if isinstance(obj, BcfKeyVal):
                g = Groups.Group(self, obj.key)
                self.all_groups[obj.key] = g

                for mem_name in obj.value.split(" "):
                    g.add(mem_name)

    def init_members(self, elm):
        for obj in elm.content_list:
            m = Groups.Member(obj.key, obj.value)
            self.all_members[m.name] = m
