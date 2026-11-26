// Active la case d'engagement seulement après lecture complète de la charte.
(function () {
  var zone = document.getElementById("charte-texte");
  var cases = document.querySelectorAll("#id_engagement");
  var aide = document.getElementById("aide-lecture");
  if (!zone || !cases.length) return;
  var caseEngagement = cases[0];
  caseEngagement.disabled = true;
  function verifier() {
    if (zone.scrollTop + zone.clientHeight >= zone.scrollHeight - 8) {
      caseEngagement.disabled = false;
      if (aide) aide.hidden = true;
      zone.removeEventListener("scroll", verifier);
    }
  }
  zone.addEventListener("scroll", verifier);
  verifier();
})();
