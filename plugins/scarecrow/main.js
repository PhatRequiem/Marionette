'use strict';
const {Plugin, PluginSettingTab, Setting, Notice} = require('obsidian');
const {Operations} = require('./operations');
const {createServer} = require('./server');
module.exports = class Scarecrow extends Plugin {
  async onload() {
    this.status = 'Starting'; this.ready = false; this.stopped = false;
    this.settings = await this.loadData();
    const plugin = this;
    this.addSettingTab(new class extends PluginSettingTab {
      display() {
        this.containerEl.empty();
        new Setting(this.containerEl).setName('Scarecrow').setDesc(plugin.status);
        new Setting(this.containerEl).setName('Read-only vault connection')
          .setDesc('Local access for Marionette. Run the project setup script to configure credentials and port. No note editing or command execution.');
      }
    }(this.app,this));
    this.registerEvent(this.app.metadataCache.on('resolved', () => {this.ready=true;}));
    this.app.workspace.onLayoutReady(() => { if (!this.stopped) this.ready=true; });
    try {
      this.server = createServer(this.settings || {}, new Operations(this.app), () => this.ready);
      this.server.on('error', () => {this.status='Offline: local listener could not start.';new Notice('Scarecrow: local listener unavailable. Check port and settings.');});
      this.server.listen(this.settings.port,'127.0.0.1', () => {this.status=`Listening on 127.0.0.1:${this.settings.port} (read-only)`;});
    } catch {this.status='Offline: run Scarecrow setup.';new Notice('Scarecrow: run the project setup script.');}
  }
  onunload() {
    this.stopped=true; this.ready=false;
    if (this.server) {this.server.close();this.server.closeAllConnections();this.server=null;}
    this.status='Offline';
  }
};
