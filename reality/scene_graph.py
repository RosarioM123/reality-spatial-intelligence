import time

class SceneGraph:
    def __init__(self, frame_id, nodes, timestamp=None):
        self.frame_id = frame_id
        self.nodes = nodes
        self.timestamp = timestamp or time.time()

    def to_json_rpc(self):
        return {
            "jsonrpc": "2.0",
            "method": "updateSceneGraph",
            "params": {
                "frame_id": self.frame_id,
                "timestamp": self.timestamp,
                "nodes": self.nodes,
            },
        }

    def diff(self, previous_graph):
        """
        Compute incremental updates between this graph and the previous one.

        TODO: Implement node-level diffing and compression strategy.
        """
        raise NotImplementedError
