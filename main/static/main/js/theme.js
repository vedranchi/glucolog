/* Light/dark switch, shared by the landing, the auth screens and the app.

   The stored choice is applied before first paint by the inline snippet in
   main/_theme_head.html; this file keeps the switch in sync and lets other
   scripts react (the glucose charts repaint on themechange). */

(function () {
  const STORAGE_KEY = "glucolog-theme";
  const root = document.documentElement;
  const switches = document.querySelectorAll("[data-theme-switch]");
  const system = window.matchMedia("(prefers-color-scheme: dark)");

  const stored = () => {
    try {
      const value = localStorage.getItem(STORAGE_KEY);
      return value === "light" || value === "dark" ? value : null;
    } catch (error) {
      return null; // private mode, or storage blocked
    }
  };

  const active = () => root.dataset.theme || (system.matches ? "dark" : "light");

  const sync = () => {
    const isDark = active() === "dark";
    switches.forEach((control) => {
      control.setAttribute("aria-checked", String(isDark));
      control.setAttribute("aria-label", isDark ? "Switch to light theme" : "Switch to dark theme");
    });
  };

  const apply = (theme) => {
    root.dataset.theme = theme;
    root.dataset.themeSource = "stored";
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (error) {
      /* the switch still works for this page view */
    }
    sync();
    document.dispatchEvent(new CustomEvent("themechange", { detail: { theme } }));
  };

  switches.forEach((control) =>
    control.addEventListener("click", () => apply(active() === "dark" ? "light" : "dark"))
  );

  // follow the system while the visitor has not chosen for themselves
  system.addEventListener("change", () => {
    if (stored()) return;
    root.dataset.theme = system.matches ? "dark" : "light";
    sync();
    document.dispatchEvent(new CustomEvent("themechange", { detail: { theme: active() } }));
  });

  sync();
})();
