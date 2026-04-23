const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("casperDesktop", {
  platform: process.platform,
});
