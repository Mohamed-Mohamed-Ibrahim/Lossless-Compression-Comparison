from abc import ABC, abstractmethod


class Compressor(ABC):
    @abstractmethod
    def compress(data):
        pass

    # @abstractmethod
    # def decompress(compressedData):
    #     pass
