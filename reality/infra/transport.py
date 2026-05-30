# Transport layer abstraction for Reality.
# This file intentionally contains only placeholders for the open-source version.

class Transport:
    """
    Base transport interface for sending scene graph updates or telemetry
    to downstream consumers (agents, dashboards, etc.).

    The real implementation is not included in the public version.
    """

    def send(self, message):
        """
        Send a message over the transport layer.

        TODO: Implement WebSocket, gRPC, or custom binary transport.
        """
        raise NotImplementedError

    def connect(self):
        """
        Establish a connection to the downstream consumer.

        TODO: Add authentication, connection pooling, and retry logic.
        """
        raise NotImplementedError

    def close(self):
        """
        Close the transport connection.

        TODO: Add graceful shutdown and cleanup.
        """
        raise NotImplementedError

