(() => {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/service-worker.js", { scope: "/" })
        .catch((error) => {
          console.warn("agent-policy service worker registration failed", error);
        });
    });
  }

  async function showBuildInfo() {
    const footer = document.querySelector("footer [role='contentinfo']") || document.querySelector("footer");
    if (!footer) return;

    const paragraph = document.createElement("p");
    paragraph.id = "documentation-build-info";
    paragraph.textContent = "最終ビルド日時を確認しています…";
    footer.appendChild(paragraph);

    try {
      const response = await fetch("/build-info.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const info = await response.json();
      const builtAt = new Date(info.built_at_utc);
      const formatted = new Intl.DateTimeFormat("ja-JP", {
        dateStyle: "long",
        timeStyle: "medium",
        timeZone: "Asia/Tokyo",
      }).format(builtAt);

      paragraph.replaceChildren();
      paragraph.append("GitHub Pages 最終ビルド: ", formatted, " (JST)");

      if (typeof info.commit === "string" && /^[0-9a-f]{40}$/.test(info.commit)) {
        const separator = document.createTextNode(" — ");
        const link = document.createElement("a");
        link.href = `https://github.com/TakashiSasaki/agent-policy/commit/${info.commit}`;
        link.textContent = info.commit.slice(0, 7);
        link.rel = "noopener noreferrer";
        paragraph.append(separator, link);
      }
    } catch (error) {
      paragraph.textContent = "GitHub Pages 最終ビルド日時を取得できませんでした。";
      console.warn("agent-policy build metadata loading failed", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showBuildInfo, { once: true });
  } else {
    showBuildInfo();
  }
})();
