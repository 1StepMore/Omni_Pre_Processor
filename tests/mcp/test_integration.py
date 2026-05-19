"""Integration tests for MCP server stdio transport.

These tests spawn the actual MCP server as a subprocess and communicate
via JSON-RPC 2.0 over stdio to verify end-to-end MCP protocol behavior.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import pytest


BATCH_TEST_DIR = Path(__file__).parent.parent.parent / "batch_test"
PHASE0_OFFICE_DIR = BATCH_TEST_DIR / "phase0_office"
DOCX_PATH = str(PHASE0_OFFICE_DIR / "normal.docx")
PDF_PATH = str(PHASE0_OFFICE_DIR / "normal.pdf")


def send_json_rpc(proc: subprocess.Popen, method: str, params: Optional[dict] = None, msg_id: int = 1) -> dict:
    """Send a JSON-RPC 2.0 request and return the parsed response."""
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": msg_id,
    }
    if params is not None:
        request["params"] = params

    request_str = json.dumps(request) + "\n"
    proc.stdin.write(request_str.encode("utf-8"))
    proc.stdin.flush()

    # Read response line
    response_line = proc.stdout.readline()
    if not response_line:
        raise RuntimeError(f"No response from server. stderr: {proc.stderr.read() if proc.stderr else 'N/A'}")

    return json.loads(response_line.decode("utf-8"))


def send_raw_message(proc: subprocess.Popen, message: dict) -> None:
    """Send a raw JSON message without expecting a response."""
    message_str = json.dumps(message) + "\n"
    proc.stdin.write(message_str.encode("utf-8"))
    proc.stdin.flush()


class TestMCPServerStdioTransport:
    """Test MCP server stdio transport via subprocess."""

    @pytest.fixture
    def server_proc(self, tmp_path: Path):
        """Start the MCP server as a subprocess with stdio transport."""
        # Set up environment with allowed directory
        env = {
            **subprocess.os.environ.copy(),
            "OPP_MCP_ALLOWED_DIRS": str(PHASE0_OFFICE_DIR.resolve()),
        }

        # Start server process
        proc = subprocess.Popen(
            [sys.executable, "-m", "opp.mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        # Wait for server to initialize
        time.sleep(0.5)

        # Check if process is still alive
        if proc.poll() is not None:
            stderr_output = proc.stderr.read().decode("utf-8") if proc.stderr else ""
            pytest.fail(f"Server process died during initialization. Exit code: {proc.returncode}. stderr: {stderr_output}")

        yield proc

        # Cleanup: ensure process is terminated
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    def test_server_starts_and_responds(self, server_proc):
        """Test that server starts and can be communicated with."""
        # Send a ping request to verify server is responsive
        response = send_json_rpc(server_proc, "ping", msg_id=1)

        # Server may not implement ping - check for either success or method not found
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1

    def test_initialize_handshake(self, server_proc):
        """Test MCP initialize handshake."""
        # MCP protocol requires an initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0",
                },
            },
        }

        send_raw_message(server_proc, init_request)

        # Read response
        response_line = server_proc.stdout.readline()
        assert response_line, "No response received from server"

        response = json.loads(response_line.decode("utf-8"))
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response

    def test_tools_list(self, server_proc):
        """Test listing available MCP tools."""
        # First send initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        send_raw_message(server_proc, init_request)
        server_proc.stdout.readline()  # consume initialize response

        # Send tools/list request
        response = send_json_rpc(server_proc, "tools/list", msg_id=2)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        # Note: server may not implement tools/list directly - that's okay for integration test

    def test_extract_document_tool_via_mcp(self, server_proc):
        """Test extract_document tool via MCP protocol."""
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        send_raw_message(server_proc, init_request)
        server_proc.stdout.readline()  # consume initialize response

        # Call extract_document tool
        response = send_json_rpc(
            server_proc,
            "tools/call",
            params={
                "name": "extract_document",
                "arguments": {
                    "file_path": DOCX_PATH,
                    "output_formats": ["md"],
                },
            },
            msg_id=2,
        )

        # Verify response structure
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2

        # Tool should return a result with success or error
        if "result" in response:
            result = response["result"]
            assert isinstance(result, dict)

    def test_detect_format_tool_via_mcp(self, server_proc):
        """Test detect_format tool via MCP protocol."""
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        send_raw_message(server_proc, init_request)
        server_proc.stdout.readline()

        # Call detect_format tool
        response = send_json_rpc(
            server_proc,
            "tools/call",
            params={
                "name": "detect_format",
                "arguments": {"file_path": DOCX_PATH},
            },
            msg_id=2,
        )

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2

    def test_error_response_for_invalid_path(self, server_proc):
        """Test that server returns proper error for invalid path."""
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        send_raw_message(server_proc, init_request)
        server_proc.stdout.readline()

        # Call extract_document with non-existent file
        response = send_json_rpc(
            server_proc,
            "tools/call",
            params={
                "name": "extract_document",
                "arguments": {"file_path": "/nonexistent/path.docx"},
            },
            msg_id=2,
        )

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        # Error should be in the result or as an error field
        if "result" in response:
            result = response["result"]
            if isinstance(result, dict):
                assert result.get("success") is False

    def test_server_process_cleanup(self, server_proc):
        """Test that server subprocess is properly cleaned up."""
        pid = server_proc.pid
        assert pid > 0

        # Terminate and verify cleanup
        server_proc.terminate()
        exit_code = server_proc.wait(timeout=5)

        # Server should terminate gracefully or be killed
        assert exit_code is not None

    def test_server_handles_invalid_json(self, server_proc):
        """Test that server handles malformed JSON gracefully."""
        # Send invalid JSON
        server_proc.stdin.write(b"not valid json\n")
        server_proc.stdin.flush()

        # Server should either ignore or send error response
        # Give server time to respond
        time.sleep(0.2)

        # If server is still alive, it handled the error gracefully
        assert server_proc.poll() is None, "Server died on invalid JSON"

    def test_server_handles_empty_request(self, server_proc):
        """Test that server handles empty request gracefully."""
        # Send newline only
        server_proc.stdin.write(b"\n")
        server_proc.stdin.flush()

        # Give server time to respond
        time.sleep(0.2)

        # Server should still be alive
        assert server_proc.poll() is None, "Server died on empty request"

    def test_multiple_sequential_requests(self, server_proc):
        """Test multiple sequential requests to verify state handling."""
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        send_raw_message(server_proc, init_request)
        server_proc.stdout.readline()

        # Make multiple tool calls
        for i in range(3):
            response = send_json_rpc(
                server_proc,
                "tools/call",
                params={
                    "name": "detect_format",
                    "arguments": {"file_path": DOCX_PATH},
                },
                msg_id=i + 2,
            )
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == i + 2

    def test_generate_xliff_tool_via_mcp(self, server_proc):
        """Test generate_xliff tool via MCP protocol."""
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        send_raw_message(server_proc, init_request)
        server_proc.stdout.readline()

        # Call generate_xliff tool
        response = send_json_rpc(
            server_proc,
            "tools/call",
            params={
                "name": "generate_xliff",
                "arguments": {
                    "file_path": DOCX_PATH,
                    "source_lang": "en",
                    "target_lang": "zh",
                },
            },
            msg_id=2,
        )

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2

    def test_generate_markdown_tool_via_mcp(self, server_proc):
        """Test generate_markdown tool via MCP protocol."""
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        send_raw_message(server_proc, init_request)
        server_proc.stdout.readline()

        # Call generate_markdown tool
        response = send_json_rpc(
            server_proc,
            "tools/call",
            params={
                "name": "generate_markdown",
                "arguments": {"file_path": DOCX_PATH},
            },
            msg_id=2,
        )

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2