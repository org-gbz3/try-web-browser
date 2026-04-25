import socket
import sys
import tkinter as tk


class URL:

    def __init__(self, url: str):
        self.schme, url = url.split("://", 1)
        assert self.schme in ("http")

        if "/" not in url:
            url = url + "/"

        self.host, url = url.split("/", 1)
        self.path = "/" + url

    def request(self):
        s = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )

        s.connect((self.host, 12345))

        request = "GET {} HTTP/1.0\r\n".format(self.path)
        request += "Host: {}\r\n".format(self.host)
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

            assert "transfer-encoding" not in response_headers
            assert "content-encoding" not in response_headers

            content = response.read()
            s.close()

            return content


def show_tk_window():
    root = tk.Tk()
    import tkinter.font as tkfont
    for name in sorted(tkfont.families()):
        print(name)
    root.title("URL Tk Probe")
    root.geometry("520x220")

    label = tk.Label(
        root,
        text=(
            "If GUI forwarding works, this Tk window should be visible on the host.\n\n"
            "Close this window or press the button below to exit."
        ),
        justify="center",
        padx=24,
        pady=24,
    )
    label.pack(expand=True, fill="both")

    button = tk.Button(root, text="Close", command=root.destroy)
    button.pack(pady=(0, 24))

    root.mainloop()


if __name__ == "__main__":
    try:
        show_tk_window()
    except tk.TclError as error:
        print(f"Failed to open Tk window: {error}", file=sys.stderr)
        raise
