'use strict';

/** A file that the viewer cannot show. The message is the plain sentence the page shows. */
class RecordingError extends Error {
  constructor(message) {
    super(message);
    this.name = 'RecordingError';
  }
}

/** A command line that the viewer cannot run. */
class ArgsError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ArgsError';
  }
}

/** A recording that the viewer cannot start. The message is the plain sentence the page shows. */
class RecordError extends Error {
  constructor(message) {
    super(message);
    this.name = 'RecordError';
  }
}

module.exports = { RecordingError, ArgsError, RecordError };
