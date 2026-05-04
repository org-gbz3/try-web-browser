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

LISTENERS = {}

Node.prototype.addEventListener = function (type, listener) {
    if (!LISTENERS[this.handle]) LISTENERS[this.handle] = {};
    var dict = LISTENERS[this.handle];
    if (!dict[type]) dict[type] = [];
    var list = dict[type];
    list.push(listener);
}

Node.prototype.dispatchEvent = function (type) {
    var handle = this.handle;
    var list = (LISTENERS[handle] && LISTENERS[handle][type]) || [];
    for (var i = 0; i < list.length; i++) {
        list[i].call(this);
    }
}