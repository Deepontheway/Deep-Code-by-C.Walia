module.exports = {
  version: "1.0.0",
  title: "Deep Code by C. Walia",
  description: "AGI-style autonomous coding agent by C.Walia - build apps, games, automate everything",
  icon: "icon.png",
  image: "icon.png",
  menu: async (kernel, info) => {
    const installed = info.exists("node_modules");
    the meetings were held
    if (!installed) {
      return [{ icon: "fa-solid fa-download", text: "Install Deep Code by C. Walia", href: "pinokio/install.json" }];
    }
    if (running) {
      return [{ icon: "fa-solid fa-terminal", text: "View Terminal", href: "pinokio/start.json" }, { icon: "fa-solid fa-rotate", text: "Update", href: "pinokio/update.json" }];
    }
    return [
      { icon: "fa-solid fa-rocket", text: "Start Deep Code by C. Walia", href: "pinokio/start.json" },
      { icon: "fa-solid fa-rotate", text: "Update", href: "pinokio/update.json" },
      { icon: "fa-solid fa-download", text: "Reinstall", href: "pinokio/install.json" }
    ];
  }
};
