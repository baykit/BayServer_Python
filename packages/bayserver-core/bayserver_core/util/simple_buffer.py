from bayserver_core.util.reusable import Reusable

class SimpleBuffer(Reusable):
    INITIAL_BUFFER_SIZE = 32768

    def __init__(self, init=INITIAL_BUFFER_SIZE):
        self.capacity = init
        self.buf = bytearray(init)
        self.length = 0


    ######################################################
    # implements Reusable
    ######################################################

    def reset(self):
        # clear for security raeson
        for i in range(self.length):
            self.buf[i] = 0
        self.length = 0

    def __len__(self):
        return self.length

    ######################################################
    # Other methods
    ######################################################

    def byte_data(self):
        return self.buf

    def put_byte(self, b):
        self.put([b], 0, 1);

    def put(self, bytes, pos=0, length=None):
        if length is None:
            length = len(bytes)

        while self.length + length > self.capacity:
            self.extend_buf()

        self.buf[self.length: self.length + length] = bytes[pos: pos + length]

        self.length += length

    def extend_buf(self):
        self.capacity *= 2
        new_buf = bytearray(self.capacity)
        new_buf[0 : self.length] = self.buf[0 : self.length]
        self.buf = new_buf
