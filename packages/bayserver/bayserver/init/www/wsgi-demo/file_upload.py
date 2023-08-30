import io
import os

class FileUpload:

    def __call__(self, *args, **kwargs):
        env = args[0]
        start_response = args[1]

        cont = []

        if env['REQUEST_METHOD'] == "GET":
            # Print form when request method is 'GET'
            cont.append("<html><body>")
            cont.append("<form method='post'  enctype='multipart/form-data' >")
            cont.append("Message: <input type='text' name='message'/><br/>")
            cont.append("File: <input type='file' name='file'/><br/>")
            cont.append("<input type='submit' value='send'/><br/>")
            cont.append("</form>")
            cont.append("</body></html>")

        else:

            cont_type = env['CONTENT_TYPE']
            p = cont_type.find("boundary=")
            boundary = "--" + cont_type[p + 9:]
            boundary = boundary.encode("utf-8")

            print(f"boundary={boundary}")

            req_in = env["wsgi.input"]
            cont_len = int(env['CONTENT_LENGTH'])

            req_cont = req_in.read(cont_len)
            #print(req_cont)

            parts = {}
            items = req_cont.split(boundary)
            for item in items:
                item = item.lstrip().decode("us-ascii")
                #print(f"item={item}")
                item_in = io.StringIO(item)
                part = {}
                while True:
                    try:
                        line = item_in.readline().strip()
                    except BaseException as e:
                        break

                    if line == "":
                       break

                    #print(f"line={line}")
                    p = line.find(":")
                    if p:
                        name = line[0:(p)].strip()
                        value = line[p + 1:].strip()
                        #print(f"{name}={value}")
                        if name.lower() == "Content-Disposition".lower():
                            value_items = value.split(";")
                            for value_item in value_items:
                                value_item = value_item.strip()

                                p = value_item.find("=")
                                if p > 0:
                                    value_item_name = value_item[0:p]
                                    value_item_value = value_item[p + 2: -1]
                                    #print(f" {value_item_name}={value_item_value}")
                                    if value_item_name:
                                        part[value_item_name] = value_item_value

                if len(part.keys()) > 0:
                    part["body"] = item_in.read(len(item)).encode("us-ascii")
                    parts[part["name"]] = part

                print(f"part={part}")

            message = parts["message"]["body"]
            file_name =  os.path.abspath(parts["file"]["filename"])
            file_cont = parts["file"]["body"]

            with open(file_name, "wb") as f:
                f.write(file_cont)

            cont.append("<html><body>")
            cont.append("Uploaded<br>")
            cont.append(f"Mesasge:{message}<br>")
            cont.append(f"FileName:{file_name}<br>")
            cont.append("</body></html>")

        start_response('200 OK', [('Content-type', 'text/html')])
        return map(lambda s : s.encode("utf-8"), cont)