/* Sprach-Lesezeichen im Footer. Das Aufrollen selbst ist reines HTML/CSS (<details>);
   dieses Skript ergänzt nur Komfort: Schließen per Klick daneben bzw. Escape und Sichtbarmachen des Menüs. */
(function () {
  "use strict";
  var details = document.querySelector(".lang-details");
  if (!details) return;
  var tab = details.querySelector("summary");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  details.addEventListener("toggle", function () {
    if (!details.open) return;
    // Der Footer wächst beim Aufrollen mit; bis zu seinem Ende scrollen, damit das ganze Menü sichtbar ist
    var footer = details.closest("footer") || details;
    if (footer.scrollIntoView) footer.scrollIntoView({ block: "end", behavior: reduceMotion ? "auto" : "smooth" });
  });
  document.addEventListener("click", function (e) {
    if (details.open && !details.contains(e.target)) details.open = false;
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && details.open) {
      details.open = false;
      tab.focus();
    }
  });
})();
