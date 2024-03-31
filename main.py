import inspect
import sys
from Blockchain import *
from GlobalBlockchainNode import *
from LocalBlockchainNode import *

localBlockChain = LocalBlockchain("nh1")
globalBLockChain = Blockchain()
facilitator = GlobalBlockchainNode(globalBLockChain)
localBlockChainNode = LocalBlockchainNode(localBlockChain)  # local node 0
bridgeLocalToGlobal = LocalBlockchainNode(localBlockChain, globalBLockChain)  # local node 1
secondBridgeLocalToGlobal = LocalBlockchainNode(localBlockChain, globalBLockChain)  # local node 2
neighborhood_map = localBlockChainNode.street_graph
edges = list(neighborhood_map.edges)

threads = []


def runServers():
    threads.append(facilitator.run_threaded())
    threads.append(localBlockChainNode.run_threaded())
    for t in bridgeLocalToGlobal.run_threaded():
        threads.append(t)
    for t in secondBridgeLocalToGlobal.run_threaded():
        threads.append(t)
    return threads


time_unit = 0.1


def simulation():
    # request facilitator until the answer
    print(f'facilitator: {facilitator.get_node_state()} {inspect.currentframe().f_lineno}')
    print("Requesting to be a facilitator")
    bridgeLocalToGlobal.request_facilitating()
    while facilitator.get_node_state() != GlobalBlockchainNodeState.WAITING_FOR_FIRST_ENCRYPTED_AVERAGE_TRAFFIC:
        sleep(time_unit)
    print(f'facilitator: {facilitator.get_node_state()} {inspect.currentframe().f_lineno}')
    while localBlockChainNode.get_node_state() != NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
        sleep(time_unit)
    print(f'localBlockChainNode {localBlockChainNode.get_node_state()} {inspect.currentframe().f_lineno}')
    while secondBridgeLocalToGlobal.get_node_state() != NeighborHoodState.FACILITATOR_REQUEST_ANSWERED:
        sleep(time_unit)
    print(f'secondBridgeLocalToGlobal {secondBridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
    # authentication with facilitator completed
    # send encrypted traffic logs
    print("Sending encrypted traffic logs")
    localBlockChainNode.send_encrypted_traffic_log(edges[0], 10)
    localBlockChainNode.send_encrypted_traffic_log(edges[1], 20)
    localBlockChainNode.send_encrypted_traffic_log(edges[0], 30)
    localBlockChainNode.send_encrypted_traffic_log(edges[1], 40)

    print(f'localBlockChainNode {localBlockChainNode.get_node_state()} {inspect.currentframe().f_lineno}')

    # wait for traffic update interval to be reached
    localBlockChainNode.debug = True
    while localBlockChainNode.get_node_state() != NeighborHoodState.ENC_AVERAGE_TRAFFIC_CALCULATION_TIME_REACHED:
        sleep(1)
    print(f'localBlockChainNode {localBlockChainNode.get_node_state()} {inspect.currentframe().f_lineno}')

    # reached the traffic update interval
    # first node to send encrypted average traffic
    print(f'First node sending encrypted average traffic {inspect.currentframe().f_lineno}')
    bridgeLocalToGlobal.add_traffic_to_chains()

    # wait for second node to get updated
    while secondBridgeLocalToGlobal.get_node_state() != NeighborHoodState.FIRST_NODE_AGGREGATED_DATA:
        sleep(time_unit)
    print(f'secondBridgeLocalToGlobal {secondBridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
    secondBridgeLocalToGlobal.add_traffic_to_chains()

    # wait for the first node to get updated
    while bridgeLocalToGlobal.get_node_state() != NeighborHoodState.SECOND_NODE_AGGREGATED_DATA:
        sleep(time_unit)
    print(f'bridgeLocalToGlobal {bridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
    bridgeLocalToGlobal.send_parameters()

    # wait for the second node to get updated
    while secondBridgeLocalToGlobal.get_node_state() != NeighborHoodState.FIRST_NODE_PARAMETERS_SENT:
        sleep(time_unit)
    print(f'secondBridgeLocalToGlobal {secondBridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
    secondBridgeLocalToGlobal.send_parameters()

    # wait for the first node to get updated
    while bridgeLocalToGlobal.get_node_state() != NeighborHoodState.SECOND_NODE_PARAMETERS_SENT:
        sleep(time_unit)
    print(f'bridgeLocalToGlobal {bridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')

    # sending decryption request
    print(f"Sending decryption request to facilitator {inspect.currentframe().f_lineno}")
    bridgeLocalToGlobal.send_decryption_request()

    # wait for the facilitator to send the decrypted average traffic
    while facilitator.get_node_state() != GlobalBlockchainNodeState.IDLE:
        sleep(time_unit)
    print(f'facilitator {facilitator.get_node_state()} {inspect.currentframe().f_lineno}')

    # wait for the first node to get updated
    print(f'bridgeLocalToGlobal {bridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')
    while bridgeLocalToGlobal.get_node_state() != NeighborHoodState.DECRYPTION_RESULT_RECEIVED:
        sleep(time_unit)
    print(f'bridgeLocalToGlobal {bridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')

    # wait for the second node to get updated
    while secondBridgeLocalToGlobal.get_node_state() != NeighborHoodState.DECRYPTION_RESULT_RECEIVED:
        sleep(time_unit)
    print(f'secondBridgeLocalToGlobal {secondBridgeLocalToGlobal.get_node_state()} {inspect.currentframe().f_lineno}')

    # approve the decryption
    print(f'Approving the decryption {inspect.currentframe().f_lineno}')

    bridgeLocalToGlobal.approve_results()


if __name__ == "__main__":
    runServers()
    simulation()
    for thread in threads:
        thread.join()
    # end all threads and exit
    sys.exit(0)
