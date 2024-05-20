from Blockchain import Blockchain, LocalBlockchain
import datetime

import SingleBlockchainScheme


class StreetMapAlreadyInBlockchainError(Exception):
    def __init__(self, block_index: int):
        message = "Street map is already in the blockchain at block with index " + str(block_index)
        self.message = message
        super().__init__(self.message)


class TwoBlockchainsNode(SingleBlockchainScheme.SingleBlockchainNode):
    def __init__(self, localBlockchain: LocalBlockchain, globalBlockchain: Blockchain, neighborhood: str, quiet=False,
                 sleep_time=0.2, traffic_update_interval_in_seconds=10):
        super().__init__(localBlockchain, neighborhood, sleep_time=sleep_time,
                         traffic_update_interva_in_seconds=traffic_update_interval_in_seconds, quiet=quiet)
        self.globalBlockchain = globalBlockchain

    def send_traffic_log(self, edge, speed):
        block_to_send = {
            "type": "traffic_speed",
            "speed": speed,
            "edge": edge,
        }
        self.blockchain.add_block(block_to_send)
        return block_to_send

    def _get_edge_average_speed(self, edge) -> float:
        block = self.blockchain.tail
        speeds = 0
        count = 0
        while block is not None and block.timestamp > self.last_update_time:
            if block.data["type"] == "traffic_speed" and block.data["edge"] == edge:
                speeds += block.data["speed"]
                count += 1
            block = block.previous_block
        if count == 0:
            return 100
        else:
            raw_average = speeds / count
            return raw_average

    def add_average_traffic_to_blockchain(self):
        start = datetime.datetime.now()
        traffic = self._calculate_neighborhood_average_traffic()
        end = datetime.datetime.now()
        self.calculating_sum_time = end - start
        block_to_send = {
            "type": "average_traffic",
            "average_traffic": traffic,
        }
        self.average_traffic_block_size = len(str(block_to_send))
        self.blockchain.add_block(block_to_send)
        self.latest_average_block = self.blockchain.tail
        self.last_update_time = datetime.datetime.now()
        block_to_send["neighborhood"] = self.neighborhood
        self.globalBlockchain.add_block(block_to_send)
