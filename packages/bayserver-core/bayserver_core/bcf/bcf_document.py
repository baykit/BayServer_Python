from bayserver_core.bcf.bcf_element import BcfElement

class BcfDocument:
    def __init__(self):
        self.content_list = []

    def print_document(self):
        self.print_content_list(self.content_list, 0)

    def print_content_list(self, list, indent):
        for o in list:
            self.print_indent(indent)
            if isinstance(o, BcfElement):
                print(f"Element({o.name}, {o.arg})")
                self.print_content_list(o.content_list, indent + 1)
                self.print_indent(indent)
                print("\n")
            else:
                print(f"KeyVal({o.key}, {o.value})")
                print("\n")


    def print_indent(self, indent):
        for i in range(indent):
            print(" ")
