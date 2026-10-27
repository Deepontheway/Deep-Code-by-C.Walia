module.exports = {
  version: "1.0.0",
  title: "WaliaCode",
  description: "Local-first coding and personal agent",
  icon: "icon.svg",
  menu: async (kernel, info) => {
    const installed = info.exists("app/venv");
    const running = info.running("start.json");
    if (!installed) {
      return [{ icon: "fa-solid fa-plug", text: "Install WaliaCode", href: "install.json" }];
    }
    if (running) {
      const state = info.local("start.json") || {};
      const menu = [{ icon: "fa-solid fa-terminal", text: "Server log", href: "start.json" }];
      if (state.url) menu.unshift({ icon: "fa-solid fa-code", text: "Open WaliaCode", href: state.url });
      menu.push({ icon: "fa-solid fa-rotate", text: "Update dependencies", href: "update.json" });
      return menu;
    }
    return [
      { icon: "fa-solid fa-rocket", text: "Start WaliaCode", href: "start.json" },
      { icon: "fa-solid fa-rotate", text: "Update dependencies", href: "update.json" },
      { icon: "fa-solid fa-plug", text: "Reinstall", href: "install.json" }
    ];
  }
};
