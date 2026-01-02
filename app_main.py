"""Application entry point for the QuizQt prototype."""

from __future__ import annotations

import socket
import sys
import ipaddress

from PySide6.QtWidgets import QApplication

from quiz_app.constants.network_constants import DEFAULT_HOST, DEFAULT_PORT
from quiz_app.core.quiz_manager import QuizManager
from quiz_app.server.api_server import start_api_server
from quiz_app.ui.teacher_main_window import TeacherMainWindow
from quiz_app.utils.logging_config import configure_logging


def _determine_student_url(port: int) -> str:
    """Best-effort determination of the local IP for student-facing URL.

    Note: When a VPN (e.g. GlobalProtect) is active, the default route can point
    to the VPN interface. In that case a simple "connect to the internet" trick
    often returns a VPN address that devices on the local Wi-Fi cannot reach.
    This function gathers multiple local IPv4 candidates and prefers typical
    LAN ranges when choosing the URL to display.
    """

    def _gather_ipv4_candidates() -> set[str]:
        candidates: set[str] = set()

        # Candidate from the route chosen for external traffic (may be VPN).
        for target in ("8.8.8.8", "1.1.1.1"):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect((target, 80))
                    candidates.add(sock.getsockname()[0])
            except OSError:
                pass

        # Candidates from hostname resolution / interface enumeration.
        try:
            for addr in socket.gethostbyname_ex(socket.gethostname())[2]:
                candidates.add(addr)
        except OSError:
            pass

        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
                sockaddr = info[4]
                if sockaddr and isinstance(sockaddr, tuple):
                    candidates.add(sockaddr[0])
        except OSError:
            pass

        return candidates

    def _rank_ipv4(address: str) -> tuple[int, str]:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return (999, address)

        if ip.version != 4:
            return (999, address)
        if ip.is_loopback:
            return (900, address)
        if ip.is_link_local:
            return (800, address)

        # Prefer private addresses, but bias away from 10/8 which is commonly
        # used by corporate VPNs.
        if ip.is_private:
            first_octet = int(str(ip).split(".", 1)[0])
            if str(ip).startswith("192.168."):
                return (0, address)
            if str(ip).startswith("172."):
                second_octet = int(str(ip).split(".", 2)[1])
                if 16 <= second_octet <= 31:
                    return (1, address)
            if first_octet == 10:
                return (2, address)
            return (3, address)

        # Public IPv4 on a local interface is less likely here, but keep as a fallback.
        return (10, address)

    candidates = _gather_ipv4_candidates()
    best = sorted(candidates, key=_rank_ipv4)[0] if candidates else None
    ip_address = best or "127.0.0.1"
    return f"http://{ip_address}:{port}/"


def main() -> None:
    """Initialize logging, start the API server, and launch the Qt UI."""
    logger = configure_logging()
    logger.info("Starting QuizQt prototype…")

    quiz_manager = QuizManager()
    # Architecture note: the QuizManager instance is still an in-memory singleton
    # shared between Qt and FastAPI. For deployments that require persistence or
    # multi-process scaling we can promote this to a small service (e.g. an
    # asyncio task or lightweight database) without changing UI/server layers.
    start_api_server(quiz_manager=quiz_manager, host=DEFAULT_HOST, port=DEFAULT_PORT)
    student_url = _determine_student_url(DEFAULT_PORT)
    logger.info("Student page available at %s", student_url)

    app = QApplication(sys.argv)
    window = TeacherMainWindow(quiz_manager=quiz_manager, student_url=student_url)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
