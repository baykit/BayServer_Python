import gzip

class GzipCompressor:
    class CompressListener:
        # interface
        # def on_compressed(*str)
        pass

    class CallbackWriter:

        def __init__(self, gzip_comp):
            self.gzip_comp = gzip_comp
            self.done_listener = None

        def write(self, buf):
            # proc
            self.gzip_comp.listener(buf, 0, len(buf), self.done_listener)

        def flush(self):
            pass


    def __init__(self, comp_lis):
        self.listener = comp_lis
        self.cb_writer = GzipCompressor.CallbackWriter(self)
        self.gfile = gzip.GzipFile(mode="wb", fileobj=self.cb_writer)

    def compress(self, buf, ofs, length, lis):
        self.cb_writer.done_listener = lis
        self.gfile.write(buf[ofs: ofs+length])

    def finish(self):
        self.gfile.flush()
        self.gfile.close()



