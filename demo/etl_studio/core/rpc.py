"""Stdio JSON-RPC 2.0 with LSP-style framing (Content-Length headers).

The Python half of the wire decided in ticket 03: the TS shim speaks
vscode-jsonrpc; this module speaks the same framing from stdlib asyncio.
Both directions run over one connection:

- server side: the shim's relayed webview requests/notifications land in
  registered handlers; ``$/cancelRequest`` cancels the in-flight handler task
  (answered with LSP error code -32800).
- client side: the core issues its own requests (the ``lm/*`` family) and can
  cancel them by sending ``$/cancelRequest``.

stdout carries frames only; all logging goes to stderr (ASCII only).
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)

REQUEST_CANCELLED = -32800  # LSP ErrorCodes.RequestCancelled
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603


class RpcError(Exception):
    """A JSON-RPC error response to one of our outgoing requests."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.data = data


class RpcClosed(Exception):
    """The connection went away (EOF on stdin / writer failed)."""


class OutgoingRequest:
    """Handle for a core-issued request: await the result, or cancel it."""

    def __init__(self, conn: "JsonRpcConnection", msg_id: int, fut: asyncio.Future):
        self._conn = conn
        self.msg_id = msg_id
        self._fut = fut

    async def wait(self) -> Any:
        return await self._fut

    def done(self) -> bool:
        return self._fut.done()

    async def cancel(self) -> None:
        """Ask the far side to cancel; it answers with -32800."""
        if not self._fut.done():
            await self._conn.notify("$/cancelRequest", {"id": self.msg_id})


RequestHandler = Callable[[Any], Awaitable[Any]]
NotificationHandler = Callable[[Any], Awaitable[None]]


class JsonRpcConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self._write_lock = asyncio.Lock()
        self._request_handlers: Dict[str, RequestHandler] = {}
        self._notification_handlers: Dict[str, NotificationHandler] = {}
        self._inflight_server: Dict[Any, asyncio.Task] = {}
        self._pending_client: Dict[int, asyncio.Future] = {}
        self._id_counter = itertools.count(1)
        self._closed = asyncio.Event()

    # ---- registration --------------------------------------------------------

    def on_request(self, method: str, handler: RequestHandler) -> None:
        self._request_handlers[method] = handler

    def on_notification(self, method: str, handler: NotificationHandler) -> None:
        self._notification_handlers[method] = handler

    # ---- outgoing ------------------------------------------------------------

    async def notify(self, method: str, params: Any = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})

    async def start_request(self, method: str, params: Any = None) -> OutgoingRequest:
        msg_id = next(self._id_counter)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_client[msg_id] = fut
        await self._send(
            {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        )
        return OutgoingRequest(self, msg_id, fut)

    async def request(self, method: str, params: Any = None) -> Any:
        req = await self.start_request(method, params)
        return await req.wait()

    # ---- wire ----------------------------------------------------------------

    async def _send(self, obj: Dict[str, Any]) -> None:
        if self._closed.is_set():
            raise RpcClosed("connection closed")
        body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        async with self._write_lock:
            try:
                self._writer.write(header + body)
                await self._writer.drain()
            except (ConnectionError, RuntimeError) as e:
                logger.error("rpc write failed: %s", e)
                self._closed.set()
                raise RpcClosed(str(e)) from e

    async def _read_message(self) -> Optional[Dict[str, Any]]:
        headers: Dict[str, str] = {}
        while True:
            line = await self._reader.readline()
            if not line:
                return None  # EOF
            text = line.decode("ascii", "replace").rstrip("\r\n")
            if text == "":
                break
            if ":" in text:
                key, value = text.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        try:
            length = int(headers.get("content-length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            logger.warning("rpc: frame without Content-Length, skipping")
            return {}
        body = await self._reader.readexactly(length)
        try:
            return json.loads(body.decode("utf-8"))
        except ValueError:
            logger.warning("rpc: unparsable frame body, skipping")
            return {}

    # ---- dispatch ------------------------------------------------------------

    async def run(self) -> None:
        """Read/dispatch until EOF. Returns when the connection dies."""
        try:
            while True:
                msg = await self._read_message()
                if msg is None:
                    logger.info("rpc: EOF on stdin, closing")
                    break
                if not msg:
                    continue
                self._dispatch(msg)
        finally:
            self._closed.set()
            for fut in self._pending_client.values():
                if not fut.done():
                    fut.set_exception(RpcClosed("connection closed"))
            self._pending_client.clear()
            for task in list(self._inflight_server.values()):
                task.cancel()

    def _dispatch(self, msg: Dict[str, Any]) -> None:
        method = msg.get("method")
        msg_id = msg.get("id")
        if method is not None and msg_id is not None:
            task = asyncio.ensure_future(self._run_request(method, msg_id, msg.get("params")))
            self._inflight_server[msg_id] = task
        elif method is not None:
            if method == "$/cancelRequest":
                self._handle_cancel(msg.get("params") or {})
            else:
                handler = self._notification_handlers.get(method)
                if handler is None:
                    logger.debug("rpc: unhandled notification %s", method)
                else:
                    asyncio.ensure_future(self._run_notification(method, handler, msg.get("params")))
        elif msg_id is not None:
            self._handle_response(msg)

    def _handle_cancel(self, params: Dict[str, Any]) -> None:
        task = self._inflight_server.get(params.get("id"))
        if task is not None and not task.done():
            task.cancel()

    def _handle_response(self, msg: Dict[str, Any]) -> None:
        fut = self._pending_client.pop(msg.get("id"), None)
        if fut is None or fut.done():
            return
        if "error" in msg and msg["error"] is not None:
            err = msg["error"]
            fut.set_exception(
                RpcError(err.get("code", INTERNAL_ERROR), err.get("message", ""), err.get("data"))
            )
        else:
            fut.set_result(msg.get("result"))

    async def _run_request(self, method: str, msg_id: Any, params: Any) -> None:
        handler = self._request_handlers.get(method)
        try:
            if handler is None:
                await self._respond_error(msg_id, METHOD_NOT_FOUND, f"method not found: {method}")
                return
            result = await handler(params)
            await asyncio.shield(self._respond(msg_id, result))
        except asyncio.CancelledError:
            await asyncio.shield(
                self._respond_error(msg_id, REQUEST_CANCELLED, "request cancelled")
            )
        except RpcClosed:
            pass
        except Exception as e:  # handler bug: answer, don't wedge the caller
            logger.exception("rpc: handler for %s raised", method)
            try:
                await self._respond_error(msg_id, INTERNAL_ERROR, f"{type(e).__name__}: {e}")
            except RpcClosed:
                pass
        finally:
            self._inflight_server.pop(msg_id, None)

    async def _run_notification(self, method: str, handler: NotificationHandler, params: Any) -> None:
        try:
            await handler(params)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("rpc: notification handler for %s raised", method)

    async def _respond(self, msg_id: Any, result: Any) -> None:
        await self._send({"jsonrpc": "2.0", "id": msg_id, "result": result})

    async def _respond_error(self, msg_id: Any, code: int, message: str, data: Any = None) -> None:
        err: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        await self._send({"jsonrpc": "2.0", "id": msg_id, "error": err})

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    async def wait_closed(self) -> None:
        await self._closed.wait()


async def stdio_connection() -> JsonRpcConnection:
    """Wire a connection over this process's stdin/stdout (POSIX)."""
    import sys

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer)
    w_transport, w_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(w_transport, w_protocol, None, loop)
    return JsonRpcConnection(reader, writer)
