/** Reader presentation of the existing audience controller's semantic state. */
(() => {
  "use strict";
  if (window.TemplatesAudienceShell) return;
  const labels = {
    en: {use: "Use templates", maintain: "Maintain templates", neutral: "Choose your journey", switch: "Reader journey", current: "Current journey"},
    ja: {use: "Use templates · 使う", maintain: "Maintain templates · 保守する", neutral: "目的を選ぶ", switch: "読者の目的", current: "現在の目的"},
  };
  function strings() {
    return labels[document.documentElement.lang?.split("-")[0]] || labels.en;
  }
  function render() {
    const audience = document.documentElement.dataset.audience || "neutral";
    const text = strings();
    let shell = document.querySelector("[data-audience-shell]");
    if (!shell) {
      shell = document.createElement("section");
      shell.dataset.audienceShell = "";
      shell.className = "audience-shell";
      shell.innerHTML = '<span class="audience-badge" data-audience-label></span><div class="audience-switcher" role="group"><button type="button" data-audience-switch="use"></button><button type="button" data-audience-switch="maintain"></button></div>';
      const main = document.querySelector(".md-container, main");
      if (!main) return;
      main.prepend(shell);
    }
    shell.hidden = audience === "neutral" && Boolean(document.querySelector(".audience-landing"));
    shell.querySelector("[data-audience-label]").textContent = text[audience] || text.neutral;
    shell.querySelector(".audience-switcher").setAttribute("aria-label", text.switch);
    for (const button of shell.querySelectorAll("[data-audience-switch]")) {
      const target = button.dataset.audienceSwitch;
      button.textContent = text[target];
      button.setAttribute("aria-pressed", String(target === audience));
      button.title = target === audience ? text.current : text[target];
    }
  }
  window.TemplatesAudienceShell = {render, strings};
  window.addEventListener("templates:audience-changed", render);
  window.addEventListener("pageshow", render);
  window.document$?.subscribe(render);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render, {once:true});
  else render();
})();
