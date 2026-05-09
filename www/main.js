console.log("Hi from JS!")

function lengthCheck() {
    var name = this.getAttribute("name");
    var value = this.getAttribute("value");
    if (value.length > 5) {
        console.log("Input " + name + " is too long!");
    }
}

inputs = document.querySelectorAll("input")
for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("keydown", lengthCheck);
}

ps = document.querySelectorAll("p")
for (var i = 0; i < ps.length; i++) {
    ps[i].innerHTML = " This is my <b>new</b> bit of content!";
}

function callback() { console.log("Callback called!"); }
setTimeout(callback, 1000);