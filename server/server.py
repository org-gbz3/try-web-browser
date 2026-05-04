import random
import socket
import urllib.parse

ENTRIES = ['Pavel was here']
SESSIONS = {}


def show_comments(session):
    out = "<!DOCTYPE html>"
    for entry in ENTRIES:
        out += "<p>{}</p>".format(entry)
    out += "<form action=add method=post>"
    out += "<p><input name=guest></p>"
    out += "<p><button>sign the book!</button></p>"
    out += "</form>"
    return out


def form_decode(body):
    params = {}
    for field in body.split("&"):
        name, value = field.split("=", 1)
        name = urllib.parse.unquote_plus(name)
        value = urllib.parse.unquote_plus(value)
        params[name] = value
    return params


def add_entry(session, params):
    if 'guest' in params:
        ENTRIES.append(params['guest'])
    return show_comments(session)


def not_found(url, method):
    out = "<!DOCTYPE html><p>Not found: {} {}".format(method, url)
    return out


def do_request(session, method, url, headers, body) -> tuple[str, str]:
    if method == "GET" and url == "/":
        return "200 OK", show_comments(session)
    elif method == "POST" and url == "/add":
        params = form_decode(body)
        add_entry(session, params)
        return "200 OK", show_comments(session)
    else:
        return "404 Not Found", not_found(url, method)


def handle_connection(conx):
    req = conx.makefile("b")
    reqline = req.readline().decode("utf8")
    method, url, version = reqline.split(" ", 2)
    assert method in ["GET", "POST"]
    headers = {}
    while True:
        line = req.readline().decode("utf8")
        if line == "\r\n":
            break
        header, value = line.split(":", 1)
        headers[header.casefold()] = value.strip()
    if "content-length" in headers:
        length = int(headers["content-length"])
        body = req.read(length).decode("utf8")
    else:
        body = None
    if "cookie" in headers:
        token = headers["cookie"][len("token="):]
    else:
        token = str(random.random())[2:]
    session = SESSIONS.setdefault(token, {})
    status, body = do_request(session, method, url, headers, body)
    response = "HTTP/1.0 {}\r\n".format(status)
    response += "Content-Length: {}\r\n".format(len(body.encode("utf8")))
    if 'cookie' not in headers:
        response += "Set-Cookie: token={}\r\n".format(token)
    response += "\r\n" + body
    conx.send(response.encode("utf8"))
    conx.close()


s = socket.socket(
    family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

s.bind(("127.0.0.1", 8000))
s.listen()

while True:
    conx, addr = s.accept()
    handle_connection(conx)
