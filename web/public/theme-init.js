// Apply saved appearance before the application paints; remains compatible with script-src 'self'.
try {
  var savedTheme = localStorage.getItem("kairos.theme");
  var resolvedTheme =
    savedTheme === "dark" ||
    (savedTheme === "system" &&
      matchMedia("(prefers-color-scheme: dark)").matches)
      ? "dark"
      : "light";
  document.documentElement.dataset.theme = resolvedTheme;
  document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
  document
    .querySelector('meta[name="theme-color"]')
    .setAttribute("content", resolvedTheme === "dark" ? "#161512" : "#f7f4ef");
} catch {
  /* Light warm neutrals remain the default if storage is unavailable. */
}
