/** Cluster bubble hover: updates cluster-hover-store for the hover card. */
(function () {
  if (window._clusterHoverInit) return;
  window._clusterHoverInit = true;

  function setClusterHover(commId) {
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props("cluster-hover-store", {
        data: commId === null || commId === undefined ? null : Number(commId),
      });
    }
  }

  document.body.addEventListener(
    "mouseover",
    function (e) {
      var bubble = e.target.closest(".cluster-bubble");
      if (!bubble) return;
      var commId = bubble.getAttribute("data-comm-id");
      if (commId) setClusterHover(commId);
    },
    true
  );

  document.body.addEventListener(
    "mouseout",
    function (e) {
      var bubble = e.target.closest(".cluster-bubble");
      if (!bubble) return;
      var related = e.relatedTarget;
      if (related && bubble.contains(related)) return;
      setClusterHover(null);
    },
    true
  );
})();
