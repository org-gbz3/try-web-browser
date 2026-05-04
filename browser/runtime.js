console = { log: function (x) { call_python("log", x); } };

function Node(handle) { this.handle = handle; }

document = {
    querySelectorAll: function (selector) {
        var handles = call_python("querySelectorAll", selector);
        return handles.map(function (handle) { return new Node(handle); });
    }
}

Node.prototype.getAttribute = function (name) {
    return call_python("getAttribute", this.handle, name);
}