from Blockchain.Blockchain import Blockchain


class LocalBlockchain(Blockchain):
    def __init__(self, neighborhood: str):
        super().__init__()
        self.neighborhood = neighborhood
