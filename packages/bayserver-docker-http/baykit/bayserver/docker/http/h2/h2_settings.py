
class H2Settings:
    DEFAULT_HEADER_TABLE_SIZE = 4096
    DEFAULT_ENABLE_PUSH = True
    DEFAULT_MAX_CONCURRENT_STREAMS = -1
    DEFAULT_MAX_WINDOW_SIZE = 65535
    DEFAULT_MAX_FRAME_SIZE = 16384
    DEFAULT_MAX_HEADER_LIST_SIZE = -1

    def __init__(self):
        self.header_table_size = None
        self.enable_push = None
        self.max_concurrent_streams = None
        self.initial_window_size = None
        self.max_frame_size = None
        self.max_header_list_size = None
        self.reset()

    def reset(self):
        self.header_table_size = H2Settings.DEFAULT_HEADER_TABLE_SIZE
        self.enable_push = H2Settings.DEFAULT_ENABLE_PUSH
        self.max_concurrent_streams = H2Settings.DEFAULT_MAX_CONCURRENT_STREAMS
        self.initial_window_size = H2Settings.DEFAULT_MAX_WINDOW_SIZE
        self.max_frame_size = H2Settings.DEFAULT_MAX_FRAME_SIZE
        self.max_header_list_size = H2Settings.DEFAULT_MAX_HEADER_LIST_SIZE
        