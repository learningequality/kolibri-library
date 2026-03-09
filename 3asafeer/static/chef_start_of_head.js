// This gets sourced as the last tag in <head>

window._localStorage = {};  // used as backedn for getStoredValue/setStoredValue

window.story = {};  // some elements in the head refer to story so better set it

// define a noop function to avoid seeing "ReferenceError: ga is not defined" error
function ga(args) { }; 
