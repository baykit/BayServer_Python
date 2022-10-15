from print_env import PrintEnv
from form_params import FormParams
from post_form_params import PostFormParams
from iter_res import IterRes
from file_wrapper import FileWrapper
from file_upload import FileUpload

class WsgiDemo:
    ITEMS = {
        "print_env" : [PrintEnv(), "Print Environment"],
        "form_params" : [FormParams(), "Form Params(get)"],
        "post_form_params" : [PostFormParams(), "Form Params(post)"],
        "iter_res" : [IterRes(), "Iterator Result"],
        "file_wrapper" : [FileWrapper(), "File Wrapper"],
        "file_upload" : [FileUpload(), "File Upload"],
    }

    def __call__(self, *args, **kwargs):
        env = args[0]
        start_response = args[1]
        self.print_env(env)

        path = env["PATH_INFO"][1:]
        item = WsgiDemo.ITEMS.get(path)
        if item:
            return item[0](env, start_response)
        else:
            return self.menu(env, start_response)

    def print_env(self, env):
        w = env['wsgi.errors']
        for key in env.keys():
            value = env[key]
            #print(f"{key}={value}")
            w.write(f"{key}={value}\n")


    def menu(self, env, start_response):
        cont = []
        cont.append("<html><body>")
        cont.append("WSGI Demos<p>")
        for key in WsgiDemo.ITEMS.keys():
            value = WsgiDemo.ITEMS[key]
            cont.append(f"<a href={key}>{value[1]}</a><br>")

        cont.append("</body></html>")
        start_response('200 OK', [('Content-type', 'text/html')])
        return map(lambda s : s.encode("utf-8"), cont)

