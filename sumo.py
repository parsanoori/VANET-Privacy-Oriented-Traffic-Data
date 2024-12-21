from lxml import etree
import math
import networkx as nx

net_file = "BerlinSumo/osm.net.xml"
route_file = "BerlinSumo/osm.passenger.trips.xml"
gml_file = "BerlinSumo/osm.net.gml"

def haversine_distance(coord1, coord2):
    """Calculate the distance between two coordinates in meters using the haversine formula."""
    R = 6371000  # Earth radius in meters
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def interpolate_coords(coord1, coord2, max_distance):
    """Split a line into smaller segments of max_distance."""
    total_distance = haversine_distance(coord1, coord2)
    if total_distance <= max_distance:
        return [coord1, coord2]

    # Calculate intermediate points
    num_segments = math.ceil(total_distance / max_distance)
    interpolated_coords = [coord1]
    for i in range(1, num_segments):
        fraction = i / num_segments
        lat = coord1[0] + fraction * (coord2[0] - coord1[0])
        lon = coord1[1] + fraction * (coord2[1] - coord1[1])
        interpolated_coords.append((lat, lon))
    interpolated_coords.append(coord2)
    return interpolated_coords


def convert_to_simple_graph(input_path, output_path):
    try:
        # Parse the XML file
        tree = etree.parse(input_path)
        root = tree.getroot()

        G = nx.Graph()  # Create an undirected graph

        nodes = set()
        edges = set()

        # Extract edges
        for edge in root.findall("edge"):
            print(edge)
            from_node_id = edge.attrib.get("from")  # Safely get the 'from' attribute
            to_node_id = edge.attrib.get("to")  # Safely get the 'to' attribute
            # print all attributes of the edge
            print(edge.attrib)
            # add from_node_id to nodes if it is not none
            if from_node_id is not None:
                nodes.add(from_node_id)
            if to_node_id is not None:
                nodes.add(to_node_id)

            # add the edge to the edges set
            edges.add((from_node_id, to_node_id))

        for node in nodes:
            G.add_node(node)

        for edge in edges:
            if edge[0] is not None and edge[1] is not None:
                G.add_edge(*edge)

        # Write the graph to a GML file
        nx.write_gml(G, output_path)
        print(f"Graph conversion completed. GML file saved to: {output_path}")

    except Exception as e:
        print(f"Error during conversion: {e}")


if __name__ == "__main__":
    convert_to_simple_graph(net_file, gml_file)
