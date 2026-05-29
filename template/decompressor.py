from abc import ABC, abstractmethod


class Decompressor(ABC):

    @abstractmethod
    def decompress(compressedData):
        pass
