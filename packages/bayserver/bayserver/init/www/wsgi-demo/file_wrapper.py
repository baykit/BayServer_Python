import io

class FileWrapper:

    def __call__(self, *args, **kwargs):
        env = args[0]
        start_response = args[1]

        data = []
        data.append("<html><body>")
        for i in range(5):
            data.append(f"Line {i + 1}<br>")
        data.append("</body></html>")

        cont = "\n".join(data)

        start_response(
            '200 OK',
            [('Content-type', 'text/html')])

        return env["wsgi.file_wrapper"](io.BytesIO(cont.encode("utf-8")), 128)
