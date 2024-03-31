# VANET-Based internet taxi service

## The protocol

The protocol is from the perspective of the nodes on the local blockchain talking to each other and the nodes on the
global blockchain.

### 1. Request facilitator

Here a **requester** from the local blockchain in the neighborhood sends a request to the global blockchain so that
someone takes responsibility of facilitating the process of calculating the traffic.

The following block type is used to send the request:

```json
{
  "type": "request_facilitator",
  "neighborhood": "neighborhood"
}
```

### 2. Facilitator accepted request

The **facilitator** from the global blockchain accepts the request and sends a message to the requester in the global
blockchain. To admit the request and send their public key so that the process can go on.

The following block type is used to accept the facilitator request on the global blockchain:

```json
{
  "type": "facilitator_accepted_request",
  "neighborhood": "neighborhood",
  "public_key": "public_key"
}
```

A node on the local chain then forwards the block to the local chain.

### 3. People in the neighborhood send their traffic data

In the local blockchain, the nodes in the neighborhood send their traffic data to the local blockchain.

The following block type is used to send the traffic data:

```json
{
  "type": "encrypted_traffic_log",
  "edge": "hash of the edge",
  "encrypted_speed": "the encrypted speed"
}
```

### 4. First node aggregating the traffic data

A node takes the responsibility of calculating the average traffic data.

To assure that the node won't send datas that are not changed the node shall make the calculation like this:

f(a,b)(E(edge_average_speed)) = a * encrypted_average_speed + b

Where a and b are random chosen numbers

The following block type is used to send the result both to the local and global chain:

```json
{
  "type": "f_ab_encrypted_average_traffic",
  "average_traffic": [
    {
      "hash of the edge": "f(a,b)(E(edge_average_speed))"
    }
  ]
}
```

### 5. Second node aggregating the traffic data

A node from the local chain takes responsibility to calculate the average traffic another time.

This node now calculates the value for each edge using the following function.

f(c,d)(E(edge_average_speed)) = c * encrypted_average_speed + d

The following block type is used to send the result both to the local and global chain.

```json
{
  "type": "f_cd_encrypted_average_traffic",
  "average_traffic": [
    {
      "hash of the edge": "f(c,d)(E(edge_average_speed))"
    }
  ]
}
```

### 6. Send the first node parameters

The first node sends the parameters a and b to the local chain.

```json
{
  "type": "first_node_parameters",
  "a": "a",
  "b": "b"
}
```

### 7. Send the second node parameters

The second node sends the parameters c and d to the local chain.

```json
{
  "type": "second_node_parameters",
  "c": "c",
  "d": "d"
}
```

### 8. Ask facilitator to send the decryption of data

A bridge node sends the following message:

```json
{
  "type": "send_decryption",
  "neighborhood": "neighborhood"
}
```

### 9. Send traffics decrypted

The facilitator now sends the decryption of the messages.

```json
{
  "type": "decrypted_average_traffic",
  "neighborhood": "neighborhood",
  "f_ab_average_traffic": [
    {
      "hash of the edge": "f(a,b)(edge_average_speed)"
    }
  ],
  "f_cd_average_traffic_two": [
    {
      "hash of the edge": "f(c,d)(edge_average_speed)"
    }
  ]
}
```

### 10. Approve Results

A node in the local chain now approves the validity of the results.
It should check the following for each node:

(f(a,b)(edge_average_speed)-b)/a == (f(c,d)(edge_average_speed)-d)/c

If approved the following is sent to the local chain.

```json
{
  "type": "approved"
}
```

else:

```json
{
  "type": "disapproved"
}
```

