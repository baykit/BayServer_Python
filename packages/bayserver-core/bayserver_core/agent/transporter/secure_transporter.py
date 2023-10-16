from bayserver_core.agent.transporter.transporter import Transporter


class SecureTransporter(Transporter):

    def __init__(self, sslctx, server_mode, buf_size, trace_ssl):
        super().__init__(server_mode, buf_size, trace_ssl)
        self.sslctx = sslctx
        self.handshaked = None

    def init(self, nb_hnd, ch, lis):
        super().init(nb_hnd, ch, lis)
        self.handshaked = False

    def reset(self):
        super().reset()
        #self.ssl_socket = None


    def __str__(self):
        return f"stp[{self.data_listener}]"


    ######################################################
    # Implements Transporter
    ######################################################

    def secure(self):
        return True

    def handshake_nonblock(self):
        return self.ch.do_handshake()

    def handshake_finished(self):
        proto = self.ch.selected_alpn_protocol()

        self.data_listener.notify_handshake_done(proto)


    def read_nonblock(self):
        return (self.ch.recv(self.capacity), None)

    def write_nonblock(self, buf, adr):
        return self.ch.send(buf)


