import selectors

from bayserver_core.bay_log import BayLog


class AcceptHandler:
    def __init__(self, agent, port_map):
        self.agent = agent
        self.port_map = port_map
        self.ch_count = 0
        self.is_shutdown = False

    def on_acceptable(self, key):
        BayLog.debug("%s on_acceptable", self.agent)
        port_dkr = self.port_map.get(key.fileobj)

        try:
            client_skt, addr = key.fileobj.accept()
        except BlockingIOError as e:
            BayLog.debug("%s Error:%s (Maybe another agent caught client socket)", self.agent, e)
            return

        BayLog.debug("%s Accepted: skt=%s", self.agent, client_skt.fileno())

        try:
            port_dkr.check_admitted(client_skt)
            client_skt.setblocking(False)
            tp = port_dkr.new_transporter(self.agent, client_skt)
        except BaseException as e:
            BayLog.error_e(e)
            client_skt.close()
            return

        # In SSL mode, since Socket object is replaced to SSLSocket, we must update "ch" variable
        client_skt = tp.ch
        self.agent.non_blocking_handler.ask_to_start(client_skt)
        self.agent.non_blocking_handler.ask_to_read(client_skt)
        self.ch_count += 1

    def on_closed(self):
        self.ch_count -= 1

    def on_busy(self):
        BayLog.debug("%s AcceptHandler:onBusy", self.agent)
        for ch in self.port_map.keys():
            self.agent.selector.unregister(ch)

    def on_free(self):
        BayLog.debug("%s AcceptHandler:onFree isShutdown=%s", self.agent, self.is_shutdown)
        if self.is_shutdown:
            return

        for ch in self.port_map.keys():
            try:
                #BayLog.debug("%s Register server socket: %d", self.agent, ch.fileno())
                self.agent.selector.register(ch, selectors.EVENT_READ)
            except BaseException as e:
                BayLog.error_e(e);

    def is_server_socket(self, ch):
        return ch in self.port_map.keys()

    def close_all(self):
        for skt in self.port_map.keys:
            BayLog.debug("%s Close server Socket: %d", self.agent, skt)
            skt.close()

    def shutdown(self):
        self.is_shutdown = True
        #self.on_busy()
        #self.agent.wakeup()