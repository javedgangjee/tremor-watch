'use strict';

// Gives the page six calls and nothing else. The page never sees Electron's
// event objects, and the record calls take no argument, so the page never
// passes a path or a command.

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('viewer', {
  openFile: () => ipcRenderer.send('viewer:open'),
  onRecording: (callback) => {
    ipcRenderer.on('viewer:recording', (_event, message) => callback(message));
  },
  reportDrawn: (report) => ipcRenderer.send('viewer:drawn', report),
  startRecording: () => ipcRenderer.send('viewer:record-start'),
  stopRecording: () => ipcRenderer.send('viewer:record-stop'),
  onRecordStatus: (callback) => {
    ipcRenderer.on('viewer:record-status', (_event, status) => callback(status));
  },
});
