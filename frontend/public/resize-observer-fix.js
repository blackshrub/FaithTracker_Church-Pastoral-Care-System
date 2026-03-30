// Suppress ResizeObserver loop limit exceeded error
// This is a known benign error from Radix UI components
// See: https://github.com/WICG/resize-observer/issues/38
window.addEventListener('error', function(e) {
    if (e.message === 'ResizeObserver loop limit exceeded' ||
        e.message === 'ResizeObserver loop completed with undelivered notifications.') {
        e.stopImmediatePropagation();
        e.stopPropagation();
        e.preventDefault();
    }
});

var _error = console.error;
console.error = function() {
    var args = Array.from(arguments);
    if (args.length > 0 && typeof args[0] === 'string' &&
        args[0].includes('ResizeObserver')) {
        return;
    }
    _error.apply(console, args);
};
