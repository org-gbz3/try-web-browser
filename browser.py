import base64
import html
import socket
import tkinter as tk
import tkinter.font
from typing import Literal
from urllib.parse import unquote_to_bytes


class URL:
    def __init__(self, url: str):
        if url.startswith("data:"):
            self.schme = "data"
            self.data_url = url
            return

        self.schme, url = url.split("://", 1)

        assert self.schme in ["http", "https", "data"]

        if self.schme == "http":
            self.port = 80
        if self.schme == "https":
            self.port = 443

        if "/" not in url:
            url = url + "/"

        self.host, url = url.split("/", 1)
        self.path = "/" + url

        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)

    def request(self):
        if self.schme == "data":
            return self._decode_data_url()

        s = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )

        s.connect((self.host, self.port))

        if self.schme == "https":
            import ssl
            ctx = ssl.create_default_context()
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            s = ctx.wrap_socket(s, server_hostname=self.host)

        request = "GET {} HTTP/1.1\r\n".format(self.path)
        request += "Host: {}\r\n".format(self.host)
        request += "Connection: close\r\n"
        request += "User-Agent: Cheap-Browser/0.1\r\n"
        request += "\r\n"

        s.send(request.encode("utf8"))

        response = s.makefile("r", encoding="utf8", newline="\r\n")

        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)

        response_headers = {}
        while True:
            line = response.readline()
            if line == "\r\n":
                break

            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        # assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        content = response.read()
        s.close()

        return content

    def _decode_data_url(self):
        payload = self.data_url[len("data:"):]
        if "," not in payload:
            raise ValueError("Invalid data URL: missing comma separator")

        metadata, raw_data = payload.split(",", 1)
        parts = [p for p in metadata.split(";") if p]
        is_base64 = False
        charset = "US-ASCII"

        for part in parts:
            if part == "base64":
                is_base64 = True
            elif part.startswith("charset="):
                charset = part.split("=", 1)[1]

        if is_base64:
            data_bytes = base64.b64decode(raw_data)
        else:
            data_bytes = unquote_to_bytes(raw_data)

        return data_bytes.decode(charset, errors="replace")


class Text:
    def __init__(self, text):
        self.text = text


class Tag:
    def __init__(self, tag):
        self.tag = tag


def lex(body):
    out = []
    buffer = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
            if buffer:
                out.append(Text(html.unescape(buffer)))
                buffer = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            buffer += c

    if not in_tag and buffer:
        out.append(Text(html.unescape(buffer)))

    return out


FONTS = {}


def get_font(size, weight, slant):
    # フォントキャッシュからフォントを取得
    key = (size, weight, slant)
    if key not in FONTS:
        # フォントを作成
        font = tkinter.font.Font(size=size, weight=weight, slant=slant)
        # パフォーマンス向上のための Label オブジェクト（Tkinter の推奨）
        label = tk.Label(font=font)
        FONTS[key] = (font, label)

    return FONTS[key][0]


WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18


class Layout:
    def __init__(self, tokens):
        self.display_list = []
        self.line = []
        self.cursor_x, self.cursor_y = HSTEP, VSTEP
        self.weight: Literal["normal", "bold"] = "normal"
        self.style: Literal["roman", "italic"] = "roman"
        self.size = 16

        for tok in tokens:
            self.token(tok)

        # 最後に残った行をフラッシュ
        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            for word in tok.text.split():
                self.word(word)

        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
        else:
            print("Unknown tag: {}".format(tok.tag))

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)

        # x座標、単語、フォントを現在の行に追加
        self.line.append((self.cursor_x, word, font))

        # カーソルが右端を超えたら改行
        if self.cursor_x + w > WIDTH - HSTEP:
            self.flush()

        self.cursor_x += w + font.measure(" ")

    def flush(self):
        # 空行では何もしない
        if not self.line:
            return

        # 行内の最大アセントを計算（レディングを考慮）
        max_ascent = max(font.metrics("ascent") for _, _, font in self.line)

        # ベースラインの y座標を計算
        baseline = self.cursor_y + 1.25 * max_ascent

        # 各単語をベースラインに合わせて配置
        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

        # 行内の最大ディセントを計算
        max_descent = max(font.metrics("descent") for _, _, font in self.line)

        # 次の行の y座標を更新（レディングを考慮）
        self.cursor_y = baseline + 1.25 * max_descent

        # xカーソルをリセットし、行バッファをクリア
        self.cursor_x = HSTEP
        self.line = []


SCROLL_STEP = 100


class Browser:
    def __init__(self):
        self.window = tk.Tk()
        self.canvas = tk.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT,
        )
        self.canvas.pack()
        self.scroll = 0

        # 下矢印キーに scrolldown メソッドをバインド
        self.window.bind("<Down>", self.scrolldown)

    def draw(self):
        self.canvas.delete("all")
        for x, y, word, font in self.display_list:
            if y > self.scroll + HEIGHT:
                continue
            if y + VSTEP < self.scroll:
                continue
            self.canvas.create_text(
                x, y - self.scroll, text=word, anchor="nw", font=font)

    def load(self, url):
        body = url.request()
        tokens = lex(body)
        self.display_list = Layout(tokens).display_list
        self.draw()

    def scrolldown(self, event):
        self.scroll += SCROLL_STEP
        self.draw()


if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tk.mainloop()
