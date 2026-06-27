import select
import socket
import ssl


def headers_to_dict(headers):
    out = {}
    for raw in headers:
        text = raw.decode("iso-8859-1", errors="replace")
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        out[key.strip().lower()] = value.strip()
    return out


def send_gateway_error(writer, code, reason):
    body = f"{code} {reason}\n".encode("utf-8")
    response = (
        f"HTTP/1.1 {code} {reason}\r\n"
        "Connection: close\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "\r\n"
    ).encode("ascii") + body
    try:
        writer.write(response)
    except Exception:
        pass


def open_upstream(upstream, timeout):
    sock = socket.create_connection((upstream["host"], upstream["port"]), timeout=timeout)
    sock.settimeout(timeout)
    if upstream["scheme"] == "https":
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=upstream["host"])
        sock.settimeout(timeout)
    return sock


def read_upstream_headers(sock):
    data = b""
    while b"\r\n\r\n" not in data and len(data) < 65536:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def connect_via_upstream(upstream, target, timeout):
    sock = open_upstream(upstream, timeout)
    request = (
        f"CONNECT {target} HTTP/1.1\r\n"
        f"Host: {target}\r\n"
        "Proxy-Connection: keep-alive\r\n"
        f"{upstream['auth']}"
        "\r\n"
    ).encode("iso-8859-1")
    sock.sendall(request)
    response = read_upstream_headers(sock)
    first_line = response.split(b"\r\n", 1)[0]
    if b" 200 " not in first_line:
        try:
            sock.close()
        except Exception:
            pass
        return None, response or first_line
    return sock, response


def relay(client_connection, upstream_sock, timeout):
    sockets = [client_connection, upstream_sock]
    for item in sockets:
        item.setblocking(False)
    try:
        while True:
            readable, _, exceptional = select.select(sockets, [], sockets, timeout)
            if exceptional or not readable:
                break
            for source in readable:
                try:
                    chunk = source.recv(65536)
                except (BlockingIOError, InterruptedError):
                    continue
                if not chunk:
                    return
                target = upstream_sock if source is client_connection else client_connection
                target.sendall(chunk)
    finally:
        try:
            upstream_sock.close()
        except Exception:
            pass


def log_warning(logger, message, extra):
    if logger:
        logger.warning(message, extra=extra)


def handle_connect_tunnel(client_connection, writer, upstream_pool, target, timeout=20, logger=None):
    if ":" not in target:
        target = f"{target}:443"
    last_error = None
    for upstream in upstream_pool.ordered_candidates():
        try:
            sock, response = connect_via_upstream(upstream, target, timeout)
            if sock:
                writer.write(response)
                relay(client_connection, sock, timeout)
                return True
            last_error = response.decode("iso-8859-1", errors="replace").splitlines()[0] if response else "upstream rejected CONNECT"
        except Exception as exc:
            last_error = str(exc)
    log_warning(logger, "Proxy gateway CONNECT failed", {"target": target, "error": last_error})
    send_gateway_error(writer, 502, "No Available Upstream Proxy")
    return False


def handle_http_proxy_request(client_connection, reader, writer, upstream_pool, method, target, version, headers, timeout=20, logger=None):
    header_map = headers_to_dict(headers)
    host = header_map.get("host")
    if not target.startswith(("http://", "https://")):
        if not host:
            send_gateway_error(writer, 400, "Missing Host Header")
            return False
        target = f"http://{host}{target}"

    body = b""
    try:
        content_length = int(header_map.get("content-length", "0"))
    except ValueError:
        content_length = 0
    if content_length > 0:
        body = reader.read(content_length)

    filtered_headers = []
    for line in headers:
        lower = line.decode("iso-8859-1", errors="replace").split(":", 1)[0].strip().lower()
        if lower in ("connection", "proxy-authorization", "proxy-connection"):
            continue
        filtered_headers.append(line)

    request_head = (
        f"{method} {target} {version}\r\n"
        + b"".join(filtered_headers).decode("iso-8859-1", errors="replace")
        + "Connection: close\r\n"
    )

    last_error = None
    for upstream in upstream_pool.ordered_candidates():
        sock = None
        try:
            sock = open_upstream(upstream, timeout)
            payload = request_head + upstream["auth"] + "\r\n"
            sock.sendall(payload.encode("iso-8859-1") + body)
            relay(client_connection, sock, timeout)
            return True
        except Exception as exc:
            last_error = str(exc)
            try:
                if sock:
                    sock.close()
            except Exception:
                pass
    log_warning(logger, "Proxy gateway HTTP failed", {"target": target, "error": last_error})
    send_gateway_error(writer, 502, "No Available Upstream Proxy")
    return False
