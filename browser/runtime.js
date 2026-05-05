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

Node.prototype.dispatchEvent = function (evt) {
    var type = evt.type;
    var list = (LISTENERS[this.handle] && LISTENERS[this.handle][type]) || [];
    for (var i = 0; i < list.length; i++) {
        list[i].call(this, evt);
    }
    return evt.do_default;
}

Object.defineProperty(Node.prototype, "innerHTML", {
    set: function (html) {
        call_python("innerHTML_set", this.handle, html.toString());
    }
});

function Event(type) {
    this.type = type;
    this.do_default = true;
}

Event.prototype.preventDefault = function () {
    this.do_default = false;
}

function XMLHttpRequest() { }

XMLHttpRequest.prototype.open = function (method, url, is_async) {
    if (is_async) throw Error("Asynchronous XHR is not supported");
    this.method = method;
    this.url = url;
}

XMLHttpRequest.prototype.send = function (payload) {
    this.responseText = call_python("XMLHttpRequest_send", this.method, this.url, payload || "");
}

SET_TIMEOUT_REQUESTS = {}

function setTimeout(callback, time_delta) {
    var handle = Object.keys(SET_TIMEOUT_REQUESTS).length;
    SET_TIMEOUT_REQUESTS[handle] = callback;
    call_python("setTimeout", handle, time_delta);
}

function __runSetTimeout(handle) {
    var callback = SET_TIMEOUT_REQUESTS[handle];
    callback();
}