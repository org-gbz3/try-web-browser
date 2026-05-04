console.log("Hi from JS!")

inputs = document.querySelectorAll("input")
for (var i = 0; i < inputs.length; i++) {
    console.log("Input: " + inputs[i].handle);
    // var name = inputs[i].getAttribute("name");
    // var value = inputs[i].getAttribute("value");
    // console.log("Input: " + name + " = " + value);
}