class IterRes:

    def __call__(self, *args, **kwargs):
        env = args[0]
        start_response = args[1]

        data = []
        data.append("<html><body>")
        for i in range(5):
            data.append(f"Line {i + 1}<br>")
        data.append("</body></html>")

        start_response(
            '200 OK',
            [('Content-type', 'text/html')])

        return iter(map(lambda s : s.encode("utf-8"), data))
