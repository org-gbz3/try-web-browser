
import base64
import ctypes
import logging
import math
import socket
from datetime import datetime
from urllib.parse import quote, unquote_to_bytes
from zoneinfo import ZoneInfo

import dukpy
import sdl2
import skia


# JST タイムゾーンの設定
def jst_converter(*args):
    return datetime.now(ZoneInfo("Asia/Tokyo")).timetuple()


# コンバーターを JST に差し替える
logging.Formatter.converter = jst_converter
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

COOKIE_JAR = {}


class URL:
    def __init__(self, url: str):
        if url.startswith("data:"):
            self.scheme = "data"
            self.data_url = url
            return

        self.scheme, url = url.split("://", 1)

        assert self.scheme in ["http", "https", "data"]

        if self.scheme == "http":
            self.port = 80
        if self.scheme == "https":
            self.port = 443

        if "/" not in url:
            url = url + "/"

        self.host, url = url.split("/", 1)
        self.path = "/" + url

        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)

    def request(self, referrer, payload=None):
        if self.scheme == "data":
            return self._decode_data_url()

        s = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )

        s.connect((self.host, self.port))

        if self.scheme == "https":
            import ssl
            ctx = ssl.create_default_context()
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            s = ctx.wrap_socket(s, server_hostname=self.host)

        method = "POST" if payload else "GET"

        request = "{} {} HTTP/1.1\r\n".format(method, self.path)
        request += "Host: {}\r\n".format(self.host)
        request += "Connection: close\r\n"
        request += "User-Agent: Cheap-Browser/0.1.5\r\n"
        if self.host in COOKIE_JAR:
            cookie, params = COOKIE_JAR[self.host]
            allow_cookie = True
            if referrer and params.get("samesite", "none") == "lax":
                if method != "GET":
                    allow_cookie = self.host == referrer.host
            if allow_cookie:
                request += "Cookie: {}\r\n".format(cookie)
        if payload:
            length = len(payload.encode("utf8"))
            request += "Content-Length: {}\r\n".format(length)
        request += "\r\n"
        if payload:
            request += payload

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

        if "set-cookie" in response_headers:
            cookie = response_headers["set-cookie"]
            params = {}
            if ";" in cookie:
                cookie, rest = cookie.split(";", 1)
                for param in rest.split(";"):
                    if "=" in param:
                        key, value = param.split("=", 1)
                    else:
                        value = "true"
                    params[key.strip().casefold()] = value.casefold()
            COOKIE_JAR[self.host] = (cookie, params)

        content = response.read()
        s.close()

        return response_headers, content

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

    def resolve(self, url):
        # 通常のURL
        if "://" in url:
            return URL(url)
        # パス相対URL
        if not url.startswith("/"):
            dir, _ = self.path.rsplit("/", 1)
            while url.startswith("../"):
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
            url = dir + "/" + url
        # スキーム相対URL
        if url.startswith("//"):
            return URL("{}:{}".format(self.scheme, url))
        # ホスト相対URL
        else:
            return URL("{}://{}:{}{}".format(self.scheme, self.host, self.port, url))

    def __str__(self) -> str:
        if self.scheme == "data":
            return self.data_url
        port_part = ":" + str(self.port)
        if self.scheme == "https" and self.port == 443:
            port_part = ""
        if self.scheme == "http" and self.port == 80:
            port_part = ""
        return "{}://{}{}{}".format(self.scheme, self.host, port_part, self.path)

    def origin(self):
        return "{}://{}:{}".format(self.scheme, self.host, self.port)


class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
        self.style = {}
        self.is_focused = False

    def __repr__(self) -> str:
        return repr(self.text)


class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent
        self.style = {}
        self.is_focused = False

    def __repr__(self) -> str:
        return "<{}>".format(self.tag)


def print_tree(node, indent=0):
    print(" " * indent + repr(node))
    for child in node.children:
        print_tree(child, indent + 2)


def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


class HTMLParser:
    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    ]
    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script"
    ]

    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def parse(self):
        text = ""
        in_tag = False
        for c in self.body:
            if c == "<":
                in_tag = True
                if text:
                    self.add_text(text)
                text = ""
            elif c == ">":
                in_tag = False
                self.add_tag(text)
                text = ""
            else:
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attrs = {}
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                # クォーテーションを削除
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attrs[key.casefold()] = value
            else:
                attrs[attrpair.casefold()] = ""
        return tag, attrs

    def add_text(self, text):
        # 空白のみのテキストノードは無視
        if text.isspace():
            return
        # 暗黙のタグを挿入
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attrs = self.get_attributes(tag)
        # DOCTYPE などの特殊なタグは無視
        if tag.startswith("!"):
            return
        # 暗黙のタグを挿入
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attrs, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attrs, parent)
            self.unfinished.append(node)

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]

            # <html> が省略されている
            if open_tags == [] and tag != "html":
                self.add_tag("html")

            # <head> または <body> が省略されている
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")

            # </head> が省略されている
            elif open_tags == ["html", "head"] and tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")

            # 未完成のタグは finish() で閉じるため、ここでは何もしない
            else:
                break

    def finish(self):
        if not self.unfinished:
            self.implicit_tags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()


class CSSParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            # プロパティ名として許容される文字が続く間、i を進める
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception(
                "Parsing error: expected word at position {}".format(self.i))
        return self.s[start:self.i]

    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception(
                "Parsing error: expected '{}' at position {}".format(literal, self.i))
        self.i += 1

    def pair(self):
        self.whitespace()
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        value = self.word()
        return prop.casefold(), value

    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None

    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop.casefold()] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def selector(self):
        out = Tagselector(self.word().casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word()
            descendant = Tagselector(tag.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except Exception:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules


class Tagselector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and node.tag == self.tag

    def __repr__(self) -> str:
        return "<TagSelector {}>".format(self.tag)


class DescendantSelector:
    def __init__(self, anncestor, descendant):
        self.anncestor = anncestor  # 先祖
        self.descendant = descendant  # 子孫
        self.priority = self.anncestor.priority + self.descendant.priority

    def matches(self, node):
        if not self.descendant.matches(node):
            return False
        while node.parent:
            if self.anncestor.matches(node.parent):
                return True
            node = node.parent
        return False

    def __repr__(self) -> str:
        return "<DescendantSelector {} {}>".format(self.anncestor, self.descendant)


FONTS = {}


def get_font(size, weight, style):
    # フォントキャッシュからフォントを取得
    key = (weight, style)
    if key not in FONTS:
        if weight == "bold":
            skia_weight = skia.FontStyle.kBold_Weight
        else:
            skia_weight = skia.FontStyle.kNormal_Weight
        if style == "italic":
            skia_style = skia.FontStyle.kItalic_Slant
        else:
            skia_style = skia.FontStyle.kUpright_Slant
        skia_width = skia.FontStyle.kNormal_Width
        style_info = skia.FontStyle(skia_weight, skia_width, skia_style)
        font = skia.Typeface('Arial', style_info)
        FONTS[key] = font
    return skia.Font(FONTS[key], size)


def linespace(font):
    metrics = font.getMetrics()
    return metrics.fDescent - metrics.fAscent


NAMED_COLORS = {
    "black": "#000000",
    "gray": "#808080",
    "white": "#ffffff",
    "red": "#ff0000",
    "green": "#00ff00",
    "blue": "#0000ff",
    "lightblue": "#add8e6",
    "lightgreen": "#90ee90",
    "orange": "#ffa500",
    "orangered": "#ff4500",
}


def parse_color(color):
    if color.startswith("#") and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return skia.Color(r, g, b)
    elif color.startswith("#") and len(color) == 9:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        a = int(color[7:9], 16)
        return skia.Color(r, g, b, a)
    elif color in NAMED_COLORS:
        return parse_color(NAMED_COLORS[color])
    else:
        return skia.ColorGRAY  # デフォルトは灰色


def parse_blend_mode(blend_mode_str):
    if blend_mode_str == "multiply":
        return skia.BlendMode.kMultiply
    elif blend_mode_str == "difference":
        return skia.BlendMode.kDifference
    elif blend_mode_str == "destination-in":
        return skia.BlendMode.kDstIn
    else:
        return skia.BlendMode.kSrcOver  # デフォルトは通常の合成


DEFAULT_STYLE_SHEET = CSSParser(open("browser/browser.css").read()).parse()
INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}


def style(node, rules):
    # デフォルトスタイルを適用
    for prop, default_val in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[prop] = node.parent.style[prop]
        else:
            node.style[prop] = default_val

    # CSSルールを適用
    for selector, body in rules:
        if not selector.matches(node):
            continue
        for prop, val in body.items():
            node.style[prop] = val

    # インラインスタイルを適用
    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for prop, val in pairs.items():
            node.style[prop] = val

    # フォントサイズは計算済みスタイル（computed style）で扱う
    if node.style["font-size"].endswith("%"):
        if node.parent:
            parent_font_size = node.parent.style["font-size"]
        else:
            parent_font_size = INHERITED_PROPERTIES["font-size"]
        node_pct = float(node.style["font-size"][:-1]) / 100
        parent_px = float(parent_font_size[:-2])
        node.style["font-size"] = "{}px".format(int(node_pct * parent_px))

    # 子ノードにスタイルを適用
    for child in node.children:
        style(child, rules)


def cascade_priority(rule):
    selector, _ = rule
    return selector.priority


WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]


class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []
        self.x: int = 0
        self.y: int = 0
        self.width: int = 0
        self.height: int = 0

    def should_paint(self):
        return True

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        # 幅は親から子へトップダウンで計算
        # 高さは子から親へボトムアップで計算
        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height

    def paint(self):
        return []

    def paint_effects(self, cmds):
        return cmds


class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x: int = 0
        self.y: int = 0
        self.width: int = 0
        self.height: int = 0

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and child.tag in BLOCK_ELEMENTS for child in self.node.children]):
            return "block"
        elif self.node.children or self.node.tag == "input":
            return "inline"
        elif self.node.children:
            return "inline"
        else:
            return "block"

    def should_paint(self):
        return isinstance(self.node, Text) or (self.node.tag != "input" and self.node.tag != "button")

    def layout(self):
        self.x = self.parent.x
        self.width = self.parent.width
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        mode = self.layout_mode()
        if mode == "block":
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next
        else:
            self.new_line()
            self.recurse(self.node)

        for child in self.children:
            child.layout()

        self.height = sum([child.height for child in self.children])

    def recurse(self, node):
        if isinstance(node, Text):
            for word in node.text.split():
                self.word(node, word)
        else:
            if node.tag == "br":
                self.new_line()
            elif node.tag in ["input", "button"]:
                self.input(node)
            else:
                for child in node.children:
                    self.recurse(child)

    def input(self, node):
        w = INPUT_WIDTH_PX
        if self.cursor_x + w > self.width:
            self.new_line()
        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        input = InputLayout(node, line, previous_word)
        line.children.append(input)

        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal":
            style = "roman"
        size = int(float(node.style["font-size"][:-2]) * .75)
        font = get_font(size, weight, style)

        self.cursor_x += w + font.measureText(" ")

    def flush(self):
        # 空行では何もしない
        if not self.line:
            return

        # 行内の最大アセントを計算（レディングを考慮）
        max_ascent = max([-font.getMetrics().fAscent
                         for _, _, font, _ in self.line])

        # ベースラインの y座標を計算
        baseline = self.cursor_y + 1.25 * max_ascent

        # 行内の最大ディセントを計算
        max_descent = max([font.getMetrics().fDescent
                          for _, _, font, _ in self.line])

        # 次の行の y座標を更新（レディングを考慮）
        self.cursor_y = baseline + 1.25 * max_descent

        # xカーソルをリセットし、行バッファをクリア
        self.cursor_x = 0
        self.line = []

    def word(self, node, word):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal":
            style = "roman"
        # レディングを考慮してフォントサイズを縮小
        size = int(float(node.style["font-size"][:-2]) * .75)

        font = get_font(size, weight, style)
        w = font.measureText(word)

        # カーソルが右端を超えたら改行
        if self.cursor_x + w > self.width:
            self.new_line()

        # 行に単語を追加
        line = self.children[-1]
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word)
        line.children.append(text)

        # カーソルを単語の幅だけ右に移動（スペース分も考慮）
        self.cursor_x += w + font.measureText(" ")

    def new_line(self):
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)

    def self_rect(self):
        return skia.Rect.MakeLTRB(self.x, self.y, self.x + self.width, self.y + self.height)

    def paint(self):
        cmds = []
        if isinstance(self.node, Element) and self.node.tag == "pre":
            rect = DrawRect(self.self_rect(), "gray")
            cmds.append(rect)
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            radius = float(self.node.style.get("border-radius", "0px")[:-2])
            rect = DrawRRect(self.self_rect(), radius, bgcolor)
            cmds.append(rect)
        return cmds

    def paint_effects(self, cmds):
        cmds = paint_visual_effects(self.node, cmds, self.self_rect())
        return cmds


class Opacity:
    def __init__(self, opacity, children):
        self.opacity = opacity
        self.children = children
        self.rect = skia.Rect.MakeEmpty()
        for cmd in self.children:
            self.rect.join(cmd.rect)

    def execute(self, canvas):
        paint = skia.Paint(
            Alphaf=self.opacity,
        )
        canvas.saveLayer(None, paint)
        for cmd in self.children:
            cmd.execute(canvas)
        canvas.restore()


class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def should_paint(self):
        return True

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        if not self.children:
            self.height = 0
            return

        # 行内の最大アセントを計算（レディングを考慮）
        max_ascent = max([-word.font.getMetrics().fAscent
                         for word in self.children])

        # ベースラインの y座標を計算
        baseline = self.y + 1.25 * max_ascent

        # 各単語をベースラインに合わせて配置
        for word in self.children:
            word.y = baseline + word.font.getMetrics().fAscent

        # 行内の最大ディセントを計算
        max_descent = max([word.font.getMetrics().fDescent
                          for word in self.children])

        # 行の高さを更新（レディングを考慮）
        self.height = 1.25 * (max_ascent + max_descent)

    def paint(self):
        return []

    def paint_effects(self, cmds):
        return cmds


class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.parent = parent
        self.previous = previous
        self.children = []
        self.y = 0  # LineLayout.layout() で配置されるまでの仮の値

    def should_paint(self):
        return True

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal":
            style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * .75)

        self.font = get_font(size, weight, style)
        self.width = self.font.measureText(self.word)

        if self.previous:
            space = self.previous.font.measureText(" ")
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = linespace(self.font)

    def paint(self):
        color = self.node.style["color"]
        return [DrawText(self.x, self.y, self.word, self.font, color)]

    def paint_effects(self, cmds):
        return cmds


INPUT_WIDTH_PX = 200


class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0

    def self_rect(self):
        return skia.Rect.MakeLTRB(self.x, self.y, self.x + self.width, self.y + self.height)

    def should_paint(self):
        return True

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal":
            style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * .75)

        self.font = get_font(size, weight, style)
        self.width = INPUT_WIDTH_PX

        if self.previous:
            space = self.previous.font.measureText(" ")
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = linespace(self.font)

    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            rect = DrawRect(self.self_rect(), bgcolor)
            cmds.append(rect)
        if self.node.tag == "input":
            text = self.node.attributes.get("value", "")
        elif self.node.tag == "button":
            if len(self.node.children) == 1 and isinstance(self.node.children[0], Text):
                text = self.node.children[0].text
            else:
                print("Ignoring HTML contents inside button")
                text = ""
        if self.node.is_focused:
            cx = self.x + self.font.measureText(text)
            cmds.append(DrawLine(cx, self.y, cx,
                        self.y + self.height, "black", 1))
        color = self.node.style["color"]
        cmds.append(DrawText(self.x, self.y, text, self.font, color))
        return cmds

    def paint_effects(self, cmds):
        return cmds


class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.text = text
        self.font = font
        self.top = y1
        self.left = x1
        self.right = x1 + font.measureText(text)
        self.bottom = y1 + linespace(font)
        self.rect = skia.Rect.MakeLTRB(x1, y1, self.right, self.bottom)
        self.color = color

    def execute(self, canvas):
        paint = skia.Paint(
            AntiAlias=True,
            Color=parse_color(self.color),
        )
        baseline = self.top - self.font.getMetrics().fAscent
        canvas.drawString(self.text, float(self.left),
                          baseline, self.font, paint)


class DrawRect:
    def __init__(self, rect, color):
        self.color = color
        self.rect = rect

    def execute(self, canvas):
        paint = skia.Paint(
            Color=parse_color(self.color),
        )
        canvas.drawRect(self.rect, paint)


class DrawRRect:
    def __init__(self, rect, radius, color):
        self.color = color
        self.rect = rect
        self.rrect = skia.RRect.MakeRectXY(rect, radius, radius)

    def execute(self, canvas):
        sk_color = parse_color(self.color)
        canvas.drawRRect(self.rrect, paint=skia.Paint(Color=sk_color))


class DrawLine:
    def __init__(self, x1, y1, x2, y2, color, thickness):
        self.rect = skia.Rect.MakeLTRB(x1, y1, x2, y2)
        self.color = color
        self.thickness = thickness

    def execute(self, canvas):
        path = (
            skia.Path()
            .moveTo(self.rect.left(), self.rect.top())
            .lineTo(self.rect.right(), self.rect.bottom())
        )
        paint = skia.Paint(
            Color=parse_color(self.color),
            StrokeWidth=self.thickness,
            Style=skia.Paint.kStroke_Style,
        )
        canvas.drawPath(path, paint)


class DrawOutline:
    def __init__(self, rect, color, thickness):
        self.rect = rect
        self.color = color
        self.thickness = thickness

    def execute(self, canvas):
        paint = skia.Paint(
            Color=parse_color(self.color),
            StrokeWidth=self.thickness,
            Style=skia.Paint.kStroke_Style,
        )
        canvas.drawRect(self.rect, paint)


class Blend:
    def __init__(self, blend_mode, children):
        self.blend_mode = blend_mode
        self.children = children
        self.rect = skia.Rect.MakeEmpty()
        for cmd in self.children:
            self.rect.join(cmd.rect)

    def execute(self, canvas):
        paint = skia.Paint(
            BlendMode=parse_blend_mode(self.blend_mode),
        )
        canvas.saveLayer(None, paint)
        for cmd in self.children:
            cmd.execute(canvas)
        canvas.restore()


def paint_tree(layout_object, display_list):
    cmds = []
    if layout_object.should_paint():
        cmds = layout_object.paint()
    for child in layout_object.children:
        paint_tree(child, display_list)

    if layout_object.should_paint():
        cmds = layout_object.paint_effects(cmds)
    display_list.extend(cmds)


def paint_visual_effects(node, cmds, rect):
    opacity = float(node.style.get("opacity", "1.0"))
    blend_mode = node.style.get("mix-blend-mode")
    if node.style.get("overflow", "visible") == "clip":
        border_radius = float(node.style.get("border-radius", "0px")[:-2])
        cmds.append(
            Blend("destination-in", [DrawRRect(rect, border_radius, "white")]))

    return [
        Blend(blend_mode, [
            Opacity(opacity, cmds)
        ]),
    ]


EVENT_DISPATCH_JS = "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type));"
RUNTIME_JS = open("browser/runtime.js").read()


class JSContext:
    def __init__(self, tab):
        self.tab = tab
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", print)
        self.interp.evaljs(RUNTIME_JS)
        self.interp.export_function("querySelectorAll", self.querySelectorAll)
        self.interp.export_function("getAttribute", self.getAttribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.node_to_handle = {}
        self.handle_to_node = {}

    def run(self, script, code):
        try:
            return self.interp.evaljs(code)
        except dukpy.JSRuntimeError as e:
            print("JavaScript error in {}: {}".format(script, e))

    def querySelectorAll(self, selector_text):
        selector = CSSParser(selector_text).selector()
        nodes = [node for node in tree_to_list(
            self.tab.nodes, []) if selector.matches(node)]
        return [self.get_handle(node) for node in nodes]

    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle) + 1
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        return self.node_to_handle[elt]

    def getAttribute(self, handle, name):
        elt = self.handle_to_node[handle]
        attr = elt.attributes.get(name, None)
        return attr if attr else ""

    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, None)
        do_default = self.interp.evaljs(
            EVENT_DISPATCH_JS, type=type, handle=handle)
        return not do_default

    def innerHTML_set(self, handle, html):
        doc = HTMLParser("<html><body>" + html + "</body></html>").parse()
        new_nodes = doc.children[0].children
        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt

        try:
            self.tab.render()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("Error while rendering after innerHTML change: {}".format(e))
            raise e

    def XMLHttpRequest_send(self, method, url, body):
        full_url = self.tab.url.resolve(url)
        if not self.tab.allowed_request(full_url):
            raise Exception(
                "Cross-origin XHR blocked by CSP: {}".format(full_url))
        headers, out = full_url.request(self.tab.url, body)
        if full_url.origin() != self.tab.url.origin():
            raise Exception("Cross-origin XHR request not allowed")
        return out


SCROLL_STEP = 100


class Tab:
    def __init__(self, tab_height):
        self.scroll = 0
        self.url: URL | None = None
        self.tab_height = tab_height
        self.history = []
        self.focus = None

    def click(self, x, y):
        self.focus = None
        assert self.url is not None
        y += self.scroll

        # クリック位置で最後の要素からヒットテスト
        objs = [obj for obj in tree_to_list(self.document, [])
                if obj.x <= x < obj.x + obj.width and obj.y <= y < obj.y + obj.height]
        if not objs:
            return
        elt = objs[-1].node
        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == "a" and "href" in elt.attributes:
                if self.js.dispatch_event("click", elt):
                    return
                url = self.url.resolve(elt.attributes["href"])
                return self.load(url)
            elif elt.tag == "input":
                if self.js.dispatch_event("click", elt):
                    return
                elt.attributes["value"] = ""
                if self.focus:
                    self.focus.is_focused = False
                self.focus = elt
                elt.is_focused = True
                return self.render()
            elif elt.tag == "button":
                if self.js.dispatch_event("click", elt):
                    return
                while elt:
                    if elt.tag == "form" and "action" in elt.attributes:
                        return self.submit_form(elt)
                    elt = elt.parent
            elt = elt.parent

    def submit_form(self, elt):
        assert self.url is not None
        if self.js.dispatch_event("submit", elt):
            return
        inputs = [node for node in tree_to_list(elt, [])
                  if isinstance(node, Element) and node.tag == "input" and "name" in node.attributes]
        body = ""
        for input in inputs:
            name = input.attributes["name"]
            name = quote(name)
            value = input.attributes.get("value", "")
            value = quote(value)
            body += "{}={}&".format(name, value)
        body = body[:-1]
        url = self.url.resolve(elt.attributes["action"])
        self.load(url, body)

    def raster(self, canvas):
        for cmd in self.display_list:
            cmd.execute(canvas)

    def load(self, url, payload=None):
        headers, body = url.request(self.url, payload)
        self.history.append(url)
        self.url = url
        logging.info("Received response: %d bytes", len(body))

        self.nodes = HTMLParser(body).parse()
        logging.info("Parsed HTML: %s", repr(self.nodes))

        self.allowed_origins = None
        if "content-security-policy" in headers:
            csp = headers["content-security-policy"].split()
            if len(csp) > 0 and csp[0] == "default-src":
                self.allowed_origins = []
                for origin in csp[1:]:
                    self.allowed_origins.append(URL(origin).origin())

        # render() が self.rules を参照するため、先に初期化しておく
        # JS 実行時に innerHTML_set() によって CSSルール適用前に render() が呼ばれる可能性があるため。
        self.rules = DEFAULT_STYLE_SHEET.copy()

        # JSを取得し実行する
        scripts = [node.attributes["src"]
                   for node in tree_to_list(self.nodes, [])
                   if isinstance(node, Element) and node.tag == "script" and "src" in node.attributes]
        self.js = JSContext(self)
        for script in scripts:
            script_url = url.resolve(script)
            script_url_s = script_url.data_url if script_url.scheme == "data" else str(
                script_url)
            if not self.allowed_request(script_url):
                logging.warning("Blocked script due to CSP: %s", script_url_s)
                continue
            try:
                header, body = script_url.request(url)
            except Exception:
                logging.warning("Failed to load script: %s", script_url_s)
                continue
            logging.info("Loaded script: %s", script_url_s)
            print("Script returned: ", self.js.run(script, body))

        # CSSルールを読み込む
        links = [node.attributes["href"]
                 for node in tree_to_list(self.nodes, [])
                 if isinstance(node, Element) and node.tag == "link"
                 and node.attributes.get("rel") == "stylesheet" and "href" in node.attributes]
        for link in links:
            style_url = url.resolve(link)
            style_url_s = style_url.data_url if style_url.scheme == "data" else str(
                style_url)
            try:
                header, body = style_url.request(url)
            except Exception:
                logging.warning("Failed to load stylesheet: %s", style_url_s)
                continue
            self.rules.extend(CSSParser(body).parse())
            logging.info("Loaded stylesheet: %s", style_url_s)
        self.render()

    def render(self):
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        # print_tree(self.document.node)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)

    def scrolldown(self):
        max_y = max(self.document.height + 2 * VSTEP - self.tab_height, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back = self.history.pop()
            self.load(back)

    def keypress(self, char):
        if self.focus:
            if self.js.dispatch_event("keydown", self.focus):
                return
            self.focus.attributes["value"] += char
            self.render()

    def allowed_request(self, url):
        return self.allowed_origins is None or url.origin() in self.allowed_origins


class Chrome:
    def __init__(self, browser):
        self.browser = browser
        self.font = get_font(20, "normal", "roman")
        self.font_height = linespace(self.font)
        self.padding = 5

        # タブバー関連のプロパティ
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2 * self.padding
        plus_width = self.font.measureText("+") + 2 * self.padding
        self.newtab_rect = skia.Rect.MakeLTRB(
            self.padding,
            self.padding,
            self.padding + plus_width,
            self.padding + self.font_height,
        )

        # URLバー関連のプロパティ
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + self.font_height + 2 * self.padding
        back_width = self.font.measureText("<") + 2 * self.padding
        self.back_rect = skia.Rect.MakeLTRB(
            self.padding,
            self.urlbar_top + self.padding,
            self.padding + back_width,
            self.urlbar_bottom - self.padding,
        )
        self.address_rect = skia.Rect.MakeLTRB(
            self.back_rect.right() + self.padding,
            self.urlbar_top + self.padding,
            WIDTH - self.padding,
            self.urlbar_bottom - self.padding,
        )
        self.focus = None
        self.address_bar = ""

        # クローム全体の高さ
        self.bottom = self.urlbar_bottom

    def tab_rect(self, i):
        tabs_start = self.newtab_rect.right() + self.padding
        tab_width = self.font.measureText("Tab X") + 2 * self.padding
        return skia.Rect.MakeLTRB(
            tabs_start + tab_width * i,
            self.tabbar_top,
            tabs_start + tab_width * (i + 1),
            self.tabbar_bottom,
        )

    def paint(self):
        cmds = []
        # クロームの背景と区切り線の描画
        cmds.append(DrawRect(skia.Rect.MakeLTRB(
            0, 0, WIDTH, self.bottom), "white"))
        cmds.append(DrawLine(0, self.bottom, WIDTH, self.bottom, "black", 1))

        # タブバーの描画
        cmds.append(DrawOutline(self.newtab_rect, "black", 1))
        cmds.append(DrawText(
            self.newtab_rect.left() + self.padding,
            self.newtab_rect.top(),
            "+",
            self.font,
            "black",
        ))
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            cmds.append(DrawLine(bounds.left(), 0, bounds.left(),
                        bounds.bottom(), "black", 1))
            cmds.append(DrawLine(bounds.right(), 0, bounds.right(),
                        bounds.bottom(), "black", 1))
            cmds.append(DrawText(
                bounds.left() + self.padding,
                bounds.top() + self.padding,
                "Tab {}".format(i + 1),
                self.font,
                "black",
            ))

            # アクティブなタブ用の追加描画
            if tab == self.browser.active_tab:
                cmds.append(DrawLine(0, bounds.bottom(), bounds.left(),
                            bounds.bottom(), "black", 1))
                cmds.append(DrawLine(bounds.right(), bounds.bottom(), WIDTH,
                            bounds.bottom(), "black", 1))

        # URLバーの描画
        cmds.append(DrawOutline(self.back_rect, "black", 1))
        cmds.append(DrawText(
            self.back_rect.left() + self.padding,
            self.back_rect.top(),
            "<",
            self.font,
            "black",
        ))
        cmds.append(DrawOutline(self.address_rect, "black", 1))
        if self.focus == "address bar":
            cmds.append(DrawText(
                self.address_rect.left() + self.padding,
                self.address_rect.top(),
                self.address_bar,
                self.font,
                "black",
            ))
            w = self.font.measureText(self.address_bar)
            cmds.append(DrawLine(
                self.address_rect.left() + self.padding + w,
                self.address_rect.top(),
                self.address_rect.left() + self.padding + w,
                self.address_rect.bottom(),
                "red",
                1,
            ))
        else:
            url = str(
                self.browser.active_tab.url) if self.browser.active_tab and self.browser.active_tab.url else ""
            cmds.append(DrawText(
                self.address_rect.left() + self.padding,
                self.address_rect.top(),
                url,
                self.font,
                "black",
            ))

        return cmds

    def click(self, x, y):
        self.focus = None
        if self.newtab_rect.contains(x, y):
            self.browser.new_tab(URL("https://browser.engineering/"))
        elif self.back_rect.contains(x, y):
            self.browser.active_tab.go_back()
        elif self.address_rect.contains(x, y):
            self.focus = "address bar"
            self.address_bar = ""
        else:
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).contains(x, y):
                    self.browser.active_tab = tab
                    break

    def keypress(self, char):
        if self.focus == "address bar":
            self.address_bar += char
            return True
        return False

    def enter(self):
        if self.focus == "address bar":
            self.browser.active_tab.load(URL(self.address_bar))
            self.focus = None

    def blur(self):
        self.focus = None


class Browser:
    def __init__(self):
        self.tabs = []
        self.active_tab: Tab | None = None
        self.sdl_window = sdl2.SDL_CreateWindow(
            b"Browser",
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            WIDTH,
            HEIGHT,
            sdl2.SDL_WINDOW_SHOWN
        )
        self.root_surface = skia.Surface.MakeRaster(
            skia.ImageInfo.Make(
                WIDTH,
                HEIGHT,
                ct=skia.kRGBA_8888_ColorType,
                at=skia.kUnpremul_AlphaType,
            )
        )
        self.chrome = Chrome(self)
        if sdl2.SDL_BYTEORDER == sdl2.SDL_BIG_ENDIAN:
            self.RED_MASK = 0xff000000
            self.GREEN_MASK = 0x00ff0000
            self.BLUE_MASK = 0x0000ff00
            self.ALPHA_MASK = 0x000000ff
        else:
            self.RED_MASK = 0x000000ff
            self.GREEN_MASK = 0x0000ff00
            self.BLUE_MASK = 0x00ff0000
            self.ALPHA_MASK = 0xff000000
        self.chrome_surface = skia.Surface(
            WIDTH, math.ceil(self.chrome.bottom))
        self.tab_surface = None

    def handle_down(self, e):
        assert self.active_tab is not None
        self.active_tab.scrolldown()
        self.draw()

    def handle_click(self, e):
        assert self.active_tab is not None
        if e.y < self.chrome.bottom:
            self.focus = None
            self.chrome.click(e.x, e.y)
            self.raster_chrome()
        else:
            self.focus = "content"
            self.chrome.blur()
            tab_y = e.y - self.chrome.bottom
            self.active_tab.click(e.x, tab_y)
            url = self.active_tab.url
            if self.active_tab.url != url:
                self.raster_chrome()
            self.raster_tab()
        self.draw()

    def raster_tab(self):
        assert self.active_tab is not None
        tab_height = math.ceil(self.active_tab.document.height + 2 * VSTEP)
        if not self.tab_surface or tab_height != self.tab_surface.height():
            self.tab_surface = skia.Surface(WIDTH, tab_height)
        canvas = self.tab_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        self.active_tab.raster(canvas)

    def raster_chrome(self):
        canvas = self.chrome_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)
        for cmd in self.chrome.paint():
            cmd.execute(canvas)

    def draw(self):
        assert self.active_tab is not None
        assert self.tab_surface is not None

        canvas = self.root_surface.getCanvas()
        canvas.clear(skia.ColorWHITE)

        # タブとクロームを合成
        tab_rect = skia.Rect.MakeLTRB(0, self.chrome.bottom, WIDTH, HEIGHT)
        tab_offset = self.chrome.bottom - self.active_tab.scroll
        canvas.save()
        canvas.clipRect(tab_rect)
        canvas.translate(0, tab_offset)
        self.tab_surface.draw(canvas, 0, 0)
        canvas.restore()
        chrome_rect = skia.Rect.MakeLTRB(0, 0, WIDTH, self.chrome.bottom)
        canvas.save()
        canvas.clipRect(chrome_rect)
        self.chrome_surface.draw(canvas, 0, 0)
        canvas.restore()

        skia_image = self.root_surface.makeImageSnapshot()
        skia_bytes = skia_image.tobytes()
        depth = 32  # ピクセルごとのビット数（４バイト）
        pitch = WIDTH * depth // 8  # 1行あたりのバイト
        sdl_surface = sdl2.SDL_CreateRGBSurfaceFrom(
            skia_bytes,
            WIDTH,
            HEIGHT,
            depth,
            pitch,
            self.RED_MASK,
            self.GREEN_MASK,
            self.BLUE_MASK,
            self.ALPHA_MASK,
        )
        rect = sdl2.SDL_Rect(0, 0, WIDTH, HEIGHT)
        window_surface = sdl2.SDL_GetWindowSurface(self.sdl_window)
        # 実際にコピーを行っているのは SDL_BlitSurface です
        sdl2.SDL_BlitSurface(sdl_surface, rect, window_surface, rect)
        sdl2.SDL_UpdateWindowSurface(self.sdl_window)

    def new_tab(self, url):
        new_tab = Tab(HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.raster_chrome()
        self.raster_tab()
        self.draw()

    def handle_key(self, e):
        assert self.active_tab is not None
        if len(e.char) == 0:
            return
        if not (0x20 <= ord(e.char) <= 0x7E):
            return
        if self.chrome.keypress(e.char):
            self.draw()
        elif self.focus == "content":
            self.active_tab.keypress(e.char)
            self.raster_tab()
            self.draw()

    def handle_enter(self, e):
        self.chrome.enter()
        self.draw()

    def handle_quit(self):
        sdl2.SDL_DestroyWindow(self.sdl_window)


def mainloop(browser):
    event = sdl2.SDL_Event()
    while True:
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_QUIT:
                browser.handle_quit()
                sdl2.SDL_Quit()
                sys.exit()
            elif event.type == sdl2.SDL_MOUSEBUTTONUP:
                browser.handle_click(event.button)
            elif event.type == sdl2.SDL_KEYDOWN:
                if event.key.keysym.sym == sdl2.SDLK_RETURN:
                    browser.handle_enter(event.key)
                elif event.key.keysym.sym == sdl2.SDLK_DOWN:
                    browser.handle_down(event.key)
            elif event.type == sdl2.SDL_TEXTINPUT:
                browser.handle_key(event.text.text.decode("utf-8"))


if __name__ == "__main__":
    import sys

    sdl2.SDL_Init(sdl2.SDL_INIT_EVENTS)
    browser = Browser()
    browser.new_tab(URL(sys.argv[1]))
    mainloop(browser)
