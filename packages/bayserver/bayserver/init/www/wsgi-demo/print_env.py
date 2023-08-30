import html

class PrintEnv:

    def __call__(self, *args, **kwargs):
        env = args[0]
        start_response = args[1]

        cont = []
        cont.append("<html><body>")
        cont.append("<table border='1'>")
        for key in env.keys():
            cont.append(f"<tr><td>{key}</td><td>{html.escape(str(env[key]))}</td></tr>")

        cont.append("</table>")
        cont.append("</body></html>")

        start_response('200 OK', [('Content-type', 'text/html')])
        return map(lambda s : s.encode("utf-8"), cont)