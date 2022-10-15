import html

class PostFormParams:

    def __call__(self, *args, **kwargs):
        env = args[0]
        start_response = args[1]

        cont_len = -1
        qstr = None

        if 'CONTENT_LENGTH' in env.keys():
            cont_len = int(env['CONTENT_LENGTH'])
        if cont_len > 0:
            qstr = env["wsgi.input"].read(cont_len).decode("utf-8")

        cont = []

        if not qstr or qstr == "":
            # request has no parameter
            cont.append("<form method='post'>")
            cont.append("First Name: <input type='text' name='fname'/><br/>")
            cont.append("Last Name: <input type='text' name='lname'/><br/>")
            cont.append("<input type='submit' value='send'/><br/>")
            cont.append("</form>")

        else:
            # request has parameters
            for param in qstr.split('&'):
                cont.append(f"{html.escape(param)}<br/>")

        start_response('200 OK', [('Content-type', 'text/html')])
        return map(lambda s : s.encode("utf-8"), cont)