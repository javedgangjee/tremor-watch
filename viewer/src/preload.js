'use strict';

// Gives the page three calls and nothing else. The page never sees Electron's
// event objects.

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('viewer', {
  openFile: () => ipcRenderer.send('viewer:open'),
  onRecording: (callback) => {
    ipcRenderer.on('viewer:recording', (_event, message) => callback(message));
  },
  reportDrawn: (report) => ipcRenderer.send('viewer:drawn', report),
});
