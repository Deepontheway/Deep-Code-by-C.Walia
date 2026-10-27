module.exports = {
  version: "1.0.0",
  title: "Walia Code",
  description: "Full-fledged autonomous coding agent - build apps, games, automate everything",
  icon: "icon.png",
  menu: async (kernel, info) => {
    const installed = info.exists("node_modules");
    const running = info.running("pinokio/start.json");
    if (!installed) {
      return [{ icon: "fa-solid fa-download", text: "Install Walia Code", href: "pinokio/install.json" }];
    }
    if (running) {
      return [{ icon: "fa-solid fa-terminal", text: "View Terminal", href: "pinokio/start.json" }, { icon: "fa-solid fa-rotate", text: "Update", href: "pinokio/update.json" }];
    }
    return [
      { icon: "fa-solid fa-rocket", text: "Start Walia Code", href: "pinokio/start.json" },
      { icon: "fa-solid fa-rotate", text: "Update", href: "pinokio/update.json" },
      { icon: "fa-solid fa-download", text: "Reinstall", href: "pinokio/install.json" }
    ];
  }
};
