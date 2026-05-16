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

function run_animation_frame() {
    if (animate()) {
        requestAnimationFrame(run_animation_frame);
    }
}

requestAnimationFrame(run_animation_frame);

var div = document.querySelectorAll("div")[0];
var total_frames = 120;
var current_frame = 0;
var change_per_frame = (0.999 - 0.1) / total_frames;

function animate() {
    current_frame++;
    var new_opacity = current_frame * change_per_frame + 0.1;
    div.style = "opacity:" + new_opacity;
    return current_frame < total_frames;
}