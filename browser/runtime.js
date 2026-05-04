console = { log: function (x) { call_python("log", x); } };

function Node(handle) { this.handle = handle; }

document = {
    querySelectorAll: function (selector) {
        var handles = call_python("querySelectorAll", selector);
        return handles.map(function (handle) { return new Node(handle); });
    }
}