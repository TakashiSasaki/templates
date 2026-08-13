"""Deterministic operation and security-sensitive lifecycle primitives."""

from __future__ import annotations

import errno
import json
import os
import re
import secrets
import socket
import stat
import time
from pathlib import Path
from typing import Callable

VERSION = "1.0.0"
CONTRACT_VERSION = 1
PID_RECORD_MAX_BYTES = 4096
HEALTH_DEADLINE_SECONDS = 2.0
HEALTH_HEADER_MAX_BYTES = 4096
HEALTH_RESPONSE_MAX_BYTES = 4096
VISIBLE_TOKEN = re.compile(r"[!-~]{32,128}\Z")
ASCII_NON_WHITESPACE = re.compile(r"[^ \t\r\n\f\v]+")


class ConfigurationError(RuntimeError):
    pass


def analyze(text: str) -> dict[str, int]:
    raw = text.encode("utf-8")
    lines = 0 if not text else text.count("\n") + (0 if text.endswith("\n") else 1)
    return {
        "bytes": len(raw),
        "lines": lines,
        "words": len(ASCII_NON_WHITESPACE.findall(text)),
    }


def process_start_ticks(pid: int) -> str | None:
    try:
        content = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    close = content.rfind(")")
    if close < 0:
        return None
    fields = content[close + 2 :].split()
    if len(fields) < 20 or not fields[19].isdigit():
        return None
    return fields[19]


def current_pid_record() -> dict[str, object]:
    ticks = process_start_ticks(os.getpid())
    if ticks is None:
        raise ConfigurationError("unable to read current process identity")
    return {"pid": os.getpid(), "startTicks": ticks}


def _no_follow_flag() -> int:
    return getattr(os, "O_NOFOLLOW", 0)


def _nonblock_flag() -> int:
    return getattr(os, "O_NONBLOCK", 0)


def _open_bounded_regular(path: Path, label: str, limit: int) -> tuple[int, os.stat_result]:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | _no_follow_flag() | _nonblock_flag(),
        )
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.EMLINK}:
            raise ConfigurationError(
                f"{label} must be a regular non-symlink file: {path}"
            ) from exc
        raise ConfigurationError(f"unable to read {label} {path}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ConfigurationError(
                f"{label} must be a regular non-symlink file: {path}"
            )
        if info.st_size > limit:
            raise ConfigurationError(f"{label} exceeds {limit} bytes: {path}")
        return descriptor, info
    except Exception:
        os.close(descriptor)
        raise


def _read_bounded_descriptor(
    descriptor: int,
    initial_info: os.stat_result,
    *,
    path: Path,
    label: str,
    limit: int,
) -> bytes:
    """Read a regular descriptor to EOF without trusting one os.read call.

    The initial fstat bounds the file before reading.  We then loop to EOF or
    limit+1 and compare the final descriptor state with both the initial size
    and the bytes actually consumed, rejecting concurrent size changes or a
    short-read prefix that did not reach EOF.
    """
    data = bytearray()
    while len(data) <= limit:
        remaining = limit + 1 - len(data)
        chunk = os.read(descriptor, min(4096, remaining))
        if not chunk:
            break
        data.extend(chunk)
    if len(data) > limit:
        raise ConfigurationError(f"{label} exceeds {limit} bytes: {path}")
    final_info = os.fstat(descriptor)
    if (
        not stat.S_ISREG(final_info.st_mode)
        or final_info.st_dev != initial_info.st_dev
        or final_info.st_ino != initial_info.st_ino
        or final_info.st_size != initial_info.st_size
        or final_info.st_size != len(data)
    ):
        raise ConfigurationError(f"{label} changed while reading: {path}")
    return bytes(data)


def read_token(path: Path | None) -> str:
    if path is None:
        raise ConfigurationError(
            "TEXT_STATS_SERVICE_TOKEN_FILE is required for service startup"
        )
    descriptor, info = _open_bounded_regular(path, "service token file", 4096)
    try:
        if info.st_uid != os.geteuid():
            raise ConfigurationError(
                f"service token file must be owned by the service user: {path}"
            )
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise ConfigurationError(
                "service token file must not be accessible by group or other users: "
                f"{path}"
            )
        raw = _read_bounded_descriptor(
            descriptor,
            info,
            path=path,
            label="service token file",
            limit=4096,
        )
    finally:
        os.close(descriptor)
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ConfigurationError(
            "service token must contain 32 to 128 visible ASCII characters"
        ) from exc
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    if VISIBLE_TOKEN.fullmatch(text) is None:
        raise ConfigurationError(
            "service token must contain 32 to 128 visible ASCII characters"
        )
    return text


def ensure_pid_record_directory(directory: Path) -> Path:
    expanded = Path(os.path.abspath(directory))
    current = Path(expanded.anchor or os.sep)
    try:
        relative_parts = expanded.parts[1:] if expanded.is_absolute() else expanded.parts
        for component in relative_parts:
            current = current / component
            created = False
            try:
                info = current.stat()
            except FileNotFoundError:
                try:
                    current.mkdir(mode=0o700)
                    created = True
                except FileExistsError:
                    pass
                if created:
                    os.chmod(current, 0o700)
                info = current.stat()
            if not stat.S_ISDIR(info.st_mode):
                raise ConfigurationError(
                    f"Headless service PID parent is not a directory: {current}"
                )
            if created and (
                info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700
            ):
                raise ConfigurationError(
                    f"Headless service PID parent failed security validation: {current}"
                )
    except ConfigurationError:
        raise
    except OSError as exc:
        raise ConfigurationError(
            f"unable to prepare headless service PID directory {directory}: {exc}"
        ) from exc
    return expanded


def _allocate_staging_file(directory: Path, basename: str) -> tuple[Path, int]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | _no_follow_flag()
    for _ in range(16):
        path = directory / (
            f".{basename}.{os.getpid()}.{secrets.token_hex(12)}.tmp"
        )
        try:
            descriptor = os.open(path, flags, 0o600)
            return path, descriptor
        except FileExistsError:
            continue
    raise ConfigurationError("unable to allocate headless service PID staging file")


def write_pid_record(
    path: Path,
    record: dict[str, object],
    *,
    write_function: Callable[[int, bytes], int] = os.write,
    before_publish: Callable[[Path, Path], None] | None = None,
) -> None:
    directory = ensure_pid_record_directory(path.parent)
    final_path = directory / path.name
    serialized = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
    if len(serialized) > PID_RECORD_MAX_BYTES:
        raise ConfigurationError(
            f"Headless service PID record exceeds {PID_RECORD_MAX_BYTES} bytes"
        )

    staging_path: Path | None = None
    descriptor: int | None = None
    linked = False
    identity: tuple[int, int] | None = None
    failure: BaseException | None = None
    try:
        staging_path, descriptor = _allocate_staging_file(directory, final_path.name)
        os.fchmod(descriptor, 0o600)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ConfigurationError(
                "Headless service PID staging file failed security validation: "
                f"{staging_path}"
            )

        offset = 0
        while offset < len(serialized):
            written = write_function(descriptor, serialized[offset:])
            if written <= 0:
                raise OSError(errno.ENOSPC, "incomplete PID-record write")
            offset += written
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        verified = bytearray()
        while len(verified) < len(serialized):
            chunk = os.read(descriptor, len(serialized) - len(verified))
            if not chunk:
                break
            verified.extend(chunk)
        if bytes(verified) != serialized:
            raise ConfigurationError(
                "unable to verify complete headless service PID record"
            )

        info = os.fstat(descriptor)
        identity = (info.st_dev, info.st_ino)
        if before_publish is not None:
            before_publish(staging_path, final_path)
        os.link(staging_path, final_path, follow_symlinks=False)
        linked = True
        published = final_path.lstat()
        if (
            not stat.S_ISREG(published.st_mode)
            or (published.st_dev, published.st_ino) != identity
        ):
            raise ConfigurationError(
                f"unable to verify published headless service PID record: {final_path}"
            )
    except FileExistsError as exc:
        failure = exc
        raise ConfigurationError(
            f"Headless service PID file already exists: {final_path}"
        ) from exc
    except ConfigurationError as exc:
        failure = exc
        raise
    except OSError as exc:
        failure = exc
        raise ConfigurationError(
            f"unable to create headless service PID file {final_path}: {exc}"
        ) from exc
    finally:
        active_failure = failure is not None or sys_exception_active()
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if active_failure and linked and identity is not None:
            try:
                current = final_path.lstat()
                if (current.st_dev, current.st_ino) == identity:
                    final_path.unlink()
            except OSError:
                pass
        if staging_path is not None:
            try:
                staging_path.unlink()
            except OSError:
                pass


def sys_exception_active() -> bool:
    import sys

    return sys.exc_info()[0] is not None


def read_pid_record(path: Path) -> dict[str, object]:
    descriptor, info = _open_bounded_regular(
        path, "Headless service PID file", PID_RECORD_MAX_BYTES
    )
    try:
        if info.st_uid != os.geteuid():
            raise ConfigurationError(
                f"Headless service PID file must be owned by the service user: {path}"
            )
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise ConfigurationError(
                f"Headless service PID file must have mode 0600: {path}"
            )
        raw = _read_bounded_descriptor(
            descriptor,
            info,
            path=path,
            label="Headless service PID file",
            limit=PID_RECORD_MAX_BYTES,
        )
    finally:
        os.close(descriptor)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Headless service PID file is invalid: {path}") from exc
    if (
        type(payload) is not dict
        or set(payload) != {"pid", "startTicks"}
        or type(payload["pid"]) is not int
        or payload["pid"] <= 0
        or type(payload["startTicks"]) is not str
        or not payload["startTicks"].isdigit()
    ):
        raise ConfigurationError(f"Headless service PID file is invalid: {path}")
    return payload


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("overall deadline exceeded")
    return remaining


def read_bounded_health_response(
    bind: str,
    port: int,
    path: str,
    *,
    deadline_seconds: float = HEALTH_DEADLINE_SECONDS,
    header_max_bytes: int = HEALTH_HEADER_MAX_BYTES,
    body_max_bytes: int = HEALTH_RESPONSE_MAX_BYTES,
) -> tuple[str, bytes]:
    deadline = time.monotonic() + deadline_seconds
    connection: socket.socket | None = None
    try:
        connection = socket.create_connection((bind, port), timeout=_remaining(deadline))
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {bind}:{port}\r\n"
            "Accept: application/json\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        connection.settimeout(_remaining(deadline))
        connection.sendall(request)

        buffered = bytearray()
        header_end = -1
        while header_end < 0:
            connection.settimeout(_remaining(deadline))
            chunk = connection.recv(512)
            if not chunk:
                raise ConfigurationError("incomplete health response")
            buffered.extend(chunk)
            header_end = buffered.find(b"\r\n\r\n")
            if header_end >= 0:
                if header_end + 4 > header_max_bytes:
                    raise ConfigurationError(
                        f"health response headers exceed {header_max_bytes} bytes"
                    )
            elif len(buffered) > header_max_bytes:
                raise ConfigurationError(
                    f"health response headers exceed {header_max_bytes} bytes"
                )

        serialized_headers = bytes(buffered[: header_end + 4])
        body = bytearray(buffered[header_end + 4 :])
        try:
            lines = serialized_headers.decode("ascii").split("\r\n")
        except UnicodeDecodeError as exc:
            raise ConfigurationError("invalid health response header") from exc
        status_match = re.fullmatch(r"HTTP/1\.[01] (\d{3})(?: .*)?", lines[0])
        if status_match is None:
            raise ConfigurationError("invalid health response status line")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line:
                continue
            if ":" not in line:
                raise ConfigurationError("invalid health response header")
            name, value = line.split(":", 1)
            if re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) is None:
                raise ConfigurationError("invalid health response header")
            headers[name.lower()] = value.strip()

        if "content-length" in headers:
            raw_length = headers["content-length"]
            if not raw_length.isascii() or not raw_length.isdigit():
                raise ConfigurationError("invalid health response Content-Length")
            length = int(raw_length, 10)
            if length > body_max_bytes:
                raise ConfigurationError(
                    f"health response exceeds {body_max_bytes} bytes"
                )
            while len(body) < length:
                connection.settimeout(_remaining(deadline))
                chunk = connection.recv(min(512, length - len(body)))
                if not chunk:
                    raise ConfigurationError("incomplete health response")
                body.extend(chunk)
            return status_match.group(1), bytes(body[:length])

        while True:
            if len(body) > body_max_bytes:
                raise ConfigurationError(
                    f"health response exceeds {body_max_bytes} bytes"
                )
            connection.settimeout(_remaining(deadline))
            chunk = connection.recv(512)
            if not chunk:
                if len(body) <= body_max_bytes:
                    return status_match.group(1), bytes(body)
                raise ConfigurationError(
                    f"health response exceeds {body_max_bytes} bytes"
                )
            body.extend(chunk)
    except socket.timeout as exc:
        raise TimeoutError("overall deadline exceeded") from exc
    finally:
        if connection is not None:
            connection.close()
