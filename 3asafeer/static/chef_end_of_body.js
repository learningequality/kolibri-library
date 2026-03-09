// This gets sourced as the last tag in <body>, so it will get executed after the
// document finishes loading but before any $(document).ready() callbacks.
window._story = window.story || {};
setTimeout(function() {
  $.extend(window.story, window._story);
  adjustReaderDimensions();
  animateButtons(0.9);            // This is necessary to force-show the buttons
}, 500);
