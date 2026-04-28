from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


SERVER_NAME = "NoiseMonitorMVP"


class SingleInstanceGuard(QObject):
    activation_requested = Signal()

    def __init__(self, server_name: str = SERVER_NAME) -> None:
        super().__init__()
        self._server_name = server_name
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._handle_new_connection)

    def start(self) -> bool:
        if self._server.listen(self._server_name):
            return True

        if self._can_notify_existing_instance():
            return False

        QLocalServer.removeServer(self._server_name)
        return self._server.listen(self._server_name)

    def close(self) -> None:
        if self._server.isListening():
            self._server.close()
        QLocalServer.removeServer(self._server_name)

    @classmethod
    def notify_existing_instance(cls, server_name: str = SERVER_NAME) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if not socket.waitForConnected(500):
            return False

        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True

    def _can_notify_existing_instance(self) -> bool:
        return self.notify_existing_instance(self._server_name)

    def _handle_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.readyRead.connect(
                lambda sock=socket: self._handle_socket_message(sock)
            )
            socket.disconnected.connect(socket.deleteLater)
            QTimer.singleShot(0, lambda sock=socket: self._handle_socket_message(sock))

    def _handle_socket_message(self, socket: QLocalSocket) -> None:
        if socket.bytesAvailable() <= 0 and not socket.waitForReadyRead(50):
            return

        payload = bytes(socket.readAll()).decode("utf-8", errors="ignore").strip()
        if payload == "show":
            self.activation_requested.emit()
        socket.disconnectFromServer()
