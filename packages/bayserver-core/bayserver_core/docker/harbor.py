from abc import ABCMeta, abstractmethod

from bayserver_core.docker.docker import Docker
from bayserver_core.docker.trouble import Trouble
from bayserver_core.sink import Sink
from bayserver_core.util.locale import Locale


class Harbor(Docker, metaclass=ABCMeta):

    MULTIPLEXER_TYPE_SPIDER = 1
    MULTIPLEXER_TYPE_SPIN = 2
    MULTIPLEXER_TYPE_PIGEON = 3
    MULTIPLEXER_TYPE_JOB = 4
    MULTIPLEXER_TYPE_TAXI = 5
    MULTIPLEXER_TYPE_TRAIN = 6

    RECIPIENT_TYPE_SPIDER = 1
    RECIPIENT_TYPE_PIPE = 2


    # Default charset 
    @abstractmethod
    def charset(self) -> str:
        pass

    
    # Default locale
    @abstractmethod
    def locale(self) -> Locale:
        pass
    
    
    # Number of grand agents
    @abstractmethod
    def grand_agents(self) -> int:
        pass
    

    # Number of train runners
    @abstractmethod
    def train_runners(self) -> int:
        pass
    

    # Number of taxi runners
    @abstractmethod
    def taxi_runners(self) -> int:
        pass
    

    # Max count of ships
    @abstractmethod
    def max_ships(self) -> int:
        pass
    

    # Trouble docker
    @abstractmethod
    def trouble(self) -> Trouble:
        pass
    

    # Socket timeout in seconds
    @abstractmethod
    def socket_timeout_sec(self) -> int:
        pass
    

    # Keep-Alive timeout in seconds
    @abstractmethod
    def keep_timeout_sec(self) -> int:
        pass
    

    # Trace req/res header flag
    @abstractmethod
    def trace_header(self) -> bool:
        pass
    

    # Internal buffer size of Tour
    @abstractmethod
    def tour_buffer_size(self) -> int:
        pass
    
    
    # File name to redirect stdout/stderr
    @abstractmethod
    def redirect_file(self) -> str:
        pass
    
    
    # Port number of signal agent
    @abstractmethod
    def control_port(self) -> int:
        pass
    

    # Gzip compression flag
    @abstractmethod
    def gzip_comp(self) -> bool:
        pass
    
    
    # Multiplexer of Network I/O
    @abstractmethod
    def net_multiplexer(self) -> int:
        pass
    

    # Multiplexer of File I/O
    @abstractmethod
    def file_multiplexer(self) -> int:
        pass
    
    
    # Multiplexer of Log output
    @abstractmethod
    def log_multiplexer(self) -> int:
        pass
    
    
    # Multiplexer of CGI input
    @abstractmethod
    def cgi_multiplexer(self) -> int:
        pass
    
    
    # Recipient
    @abstractmethod
    def recipient(self) -> int:
        pass

    # PID file name
    @abstractmethod
    def pid_file(self) -> str:
        pass
    
    # Multi core flag
    @abstractmethod
    def multi_core(self) -> bool:
        pass

    @classmethod
    def get_multiplexer_type_name(cls, type: int) -> str:
        if type == Harbor.MULTIPLEXER_TYPE_SPIDER:
            return "spider"
        elif type == Harbor.MULTIPLEXER_TYPE_SPIN:
            return "spin"
        elif type == Harbor.MULTIPLEXER_TYPE_PIGEON:
            return "pigeon"
        elif type == Harbor.MULTIPLEXER_TYPE_JOB:
            return "job"
        elif type == Harbor.MULTIPLEXER_TYPE_TAXI:
            return "taxi"
        elif type == Harbor.MULTIPLEXER_TYPE_TRAIN:
            return "train"
        else:
            return None

    @classmethod
    def get_multiplexer_type(cls, type: str) -> int:
        if type is not None:
            type = type.lower()

        if type == "spider":
            return cls.MULTIPLEXER_TYPE_SPIDER
        elif type == "spin":
            return cls.MULTIPLEXER_TYPE_SPIN
        elif type == "pigeon":
            return cls.MULTIPLEXER_TYPE_PIGEON
        elif type == "job":
            return cls.MULTIPLEXER_TYPE_JOB
        elif type == "taxi":
            return cls.MULTIPLEXER_TYPE_TAXI
        elif type == "train":
            return cls.MULTIPLEXER_TYPE_TRAIN
        else:
            raise Sink()


    @classmethod
    def get_recipient_type_name(cls, type: int) -> str:
        if type == Harbor.RECIPIENT_TYPE_SPIDER:
            return "spider"
        elif type == Harbor.RECIPIENT_TYPE_PIPE:
            return "pipe"
        else:
            return None

    @classmethod
    def get_recipient_type(cls, type: str) -> int:
        if type is not None:
            type = type.lower()

        if type == "spider":
            return cls.RECIPIENT_TYPE_SPIDER
        elif type == "pipe":
            return cls.RECIPIENT_TYPE_PIPE
        else:
            raise Sink()