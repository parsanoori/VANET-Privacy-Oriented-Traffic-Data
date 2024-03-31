from typing import Dict

from Blockchain import Blockchain
from BlockchainNode import BlockchainNode
from phe import paillier

from enum import Enum

from time import sleep
import threading


class GlobalBlockchainNodeState(Enum):
    IDLE = 0
    WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC = 1
    WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC = 2
    WAITING_FOR_DECRYPTION_REQUEST = 3


class InvalidStateError(Exception):
    def __init__(self, state: GlobalBlockchainNodeState, action: str):
        self.state = state
        self.action = action
        self.message = f'Cannot perform action {action} while in state {state}'


class GlobalBlockchainNode(BlockchainNode):
    def __init__(self, blockchain: Blockchain):
        super().__init__(blockchain)
        self.f_ab_decrypted_average_traffic: Dict[str, float] = {}
        self.f_cd_decrypted_average_traffic: Dict[str, float] = {}
        self.key_pair = paillier.generate_paillier_keypair()
        self.state = GlobalBlockchainNodeState.IDLE
        self.current_neighborhood = None
        self.thread = threading.Thread(target=self.run)

    def run_threaded(self):
        self.thread.start()
        return self.thread

    def get_node_state(self):
        return self.state

    def run(self):
        while True:
            if self.state == GlobalBlockchainNodeState.IDLE:
                self.listen_for_facilitating_request()
            elif self.state == GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
                self.listen_for_first_encrypted_average_traffic()
            elif self.state == GlobalBlockchainNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC:
                self.listen_for_second_encrypted_average_traffic()
            elif self.state == GlobalBlockchainNodeState.WAITING_FOR_DECRYPTION_REQUEST:
                self.listen_for_decryption_request()
            else:
                raise InvalidStateError(self.state, "run_server")

    def listen_for_facilitating_request(self):
        if self.state != GlobalBlockchainNodeState.IDLE:
            raise InvalidStateError(self.state, "listen_for_pubkey_request")

        while self.check_and_answer_facilitating_request() is False:
            sleep(0.1)

    def check_and_answer_facilitating_request(self):
        if self.state != GlobalBlockchainNodeState.IDLE:
            raise InvalidStateError(self.state, "check_answer_facilitating_request")

        latest_block = self.blockchain.tail
        if latest_block.data["type"] == "request_facilitator":
            self.blockchain.add_block({
                "type": "facilitator_accepted_request",
                "neighborhood": latest_block.data["neighborhood"],
                "public_key": str(self.key_pair[0].n)
            })
            self.state = GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC
            self.current_neighborhood = latest_block.data["neighborhood"]
            print(f'global node {self.node_id} accepted request for neighborhood {self.current_neighborhood}')
            return True
        return False

    def get_average_traffic(self, average_encrypted: Dict[str, int]) -> Dict[str, int]:
        average_traffic = {}
        for key, value in average_encrypted.items():
            average_traffic[key] = self.key_pair[1].raw_decrypt(value)
        return average_traffic

    def check_for_first_encrypted_average_traffic(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
            raise InvalidStateError(self.state, "checkForFirstEncryptedAverageTraffic")
        latest_block = self.blockchain.tail
        if latest_block.data["neighborhood"] != self.current_neighborhood:
            return False
        if latest_block.data["type"] == "f_ab_encrypted_average_traffic":
            self.f_ab_decrypted_average_traffic = self.get_average_traffic(latest_block.data["average_traffic"])
            self.state = GlobalBlockchainNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC
            print(f"global node {self.node_id} received f_ab_encrypted_average_traffic")
            return True
        return False

    def check_for_second_encrypted_average_traffic(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC:
            raise InvalidStateError(self.state, "checkForSecondEncryptedAverageTraffic")
        latest_block = self.blockchain.tail
        if latest_block.data["neighborhood"] != self.current_neighborhood:
            return False
        if latest_block.data["type"] == "f_cd_encrypted_average_traffic":
            self.f_cd_decrypted_average_traffic = self.get_average_traffic(latest_block.data["average_traffic"])
            self.state = GlobalBlockchainNodeState.WAITING_FOR_DECRYPTION_REQUEST
            print(f"global node {self.node_id} received f_cd_encrypted_average_traffic")
            return True
        return False

    def listen_for_first_encrypted_average_traffic(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
            raise InvalidStateError(self.state, "listen_for_first_encrypted_average_traffic")
        while self.check_for_first_encrypted_average_traffic() is False:
            sleep(0.1)

    def listen_for_second_encrypted_average_traffic(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_SECOND_ENCRYPTED_AVERAGE_TRAFFIC:
            raise InvalidStateError(self.state, "listen_for_second_encrypted_average_traffic")
        while self.check_for_second_encrypted_average_traffic() is False:
            sleep(0.1)

    def check_and_answer_decryption_request(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_DECRYPTION_REQUEST:
            raise InvalidStateError(self.state, "check_and_answer_decryption_request")

        latest_block = self.blockchain.tail
        if latest_block.data["neighborhood"] != self.current_neighborhood:
            return False

        if latest_block.data["type"] == "send_decryption":
            self.blockchain.add_block({
                "type": "decrypted_average_traffic",
                "neighborhood": self.current_neighborhood,
                "f_ab_decrypted_average_traffic": self.f_ab_decrypted_average_traffic,
                "f_cd_decrypted_average_traffic": self.f_cd_decrypted_average_traffic
            })
            self.state = GlobalBlockchainNodeState.IDLE
            print(f"global node {self.node_id} sent decryption_response now moving on to the next requests")
            return True

        return False

    def listen_for_decryption_request(self):
        if self.state != GlobalBlockchainNodeState.WAITING_FOR_DECRYPTION_REQUEST:
            raise InvalidStateError(self.state, "listen_for_decryption_request")
        while self.check_and_answer_decryption_request() is False:
            sleep(0.1)
