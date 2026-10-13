// Nova website: menu, theme, tabs, page highlight, and gentle reveal-on-scroll. Loaded on every page.
const root = document.documentElement;
const menuButton = document.querySelector(".menu-btn");
const navLinks = document.querySelector(".nav-links");

// Open and close the menu on small screens (the three-line button).
menuButton.addEventListener("click", () => {
  const isOpen = navLinks.classList.toggle("open");
  menuButton.setAttribute("aria-expanded", String(isOpen));
});
document.addEventListener("click", (event) => {
  if (navLinks.classList.contains("open") && !event.target.closest(".nav")) { navLinks.classList.remove("open"); menuButton.setAttribute("aria-expanded", "false"); }
});

// Highlight the link that matches the current page.
const currentPage = location.pathname.split("/").pop() || "index.html";
document.querySelectorAll(".nav-links a").forEach((link) => {
  if (link.getAttribute("href") === currentPage) { link.classList.add("active"); link.setAttribute("aria-current", "page"); }
});

// Light / dark: follows the computer until the visitor picks one.
const themeButton = document.querySelector(".theme-btn");
const sunIcon = '<svg class="icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
const moonIcon = '<svg class="icon" viewBox="0 0 24 24"><path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/></svg>';
function setTheme(mode, save) {
  root.dataset.theme = mode;
  themeButton.innerHTML = mode === "dark" ? sunIcon : moonIcon;
  if (save) { try { localStorage.setItem("nova-theme", mode); } catch (error) { /* private mode: it just will not be remembered */ } }
}
let saved = null; try { saved = localStorage.getItem("nova-theme"); } catch (error) { /* ignore */ }
setTheme(saved || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"), false);
themeButton.addEventListener("click", () => setTheme(root.dataset.theme === "dark" ? "light" : "dark", true));

// Use real glass refraction where the browser can do it (Chromium).
if (window.chrome) root.classList.add("has-lens");

// Advantages / Risks tabs (only on the Tech in Education page).
const tabs = document.querySelectorAll(".tab");
tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((other) => {
      const isActive = other === tab;
      other.setAttribute("aria-selected", String(isActive));
      document.getElementById(other.dataset.panel).hidden = !isActive;
    });
  });
});

// A light that follows the pointer across glass.
let frame = 0, lastEvent = null;
document.addEventListener("pointermove", (event) => {
  lastEvent = event; if (frame) return;
  frame = requestAnimationFrame(() => {
    frame = 0; const glass = lastEvent.target.closest && lastEvent.target.closest(".glass"); if (!glass) return;
    const box = glass.getBoundingClientRect(); glass.style.setProperty("--mx", (lastEvent.clientX - box.left) + "px"); glass.style.setProperty("--my", (lastEvent.clientY - box.top) + "px");
  });
}, { passive: true });

// Sections glide in as you scroll. Without IntersectionObserver (or with reduced motion) everything just shows.
const blocks = document.querySelectorAll(".section, .page-head, .hero .container");
if ("IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const seen = new IntersectionObserver((entries) => entries.forEach((entry) => { if (entry.isIntersecting) { entry.target.classList.add("in"); seen.unobserve(entry.target); } }), { threshold: 0.08 });
  blocks.forEach((block) => { block.classList.add("reveal"); seen.observe(block); });
}
