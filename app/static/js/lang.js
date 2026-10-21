/* Sprach-Lesezeichen im Footer. Das Aufrollen selbst ist reines HTML/CSS (<details>);
   dieses Skript ergänzt nur Komfort: Schließen per Klick daneben bzw. Escape. */
(function () {
  "use strict";
  var details = document.querySelector(".lang-details");
  if (!details) return;
  var tab = details.querySelector("summary");

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
