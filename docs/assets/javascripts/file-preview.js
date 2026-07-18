(() => {
  "use strict";

  const MANIFEST_URL = "/generated/repository-preview/index.json";
  let manifestPromise;

  function loadManifest() {
    if (!manifestPromise) {
      manifestPromise = fetch(MANIFEST_URL, { cache: "no-store" }).then((response) => {
        if (!response.ok) throw new Error(`Preview manifest request failed: ${response.status}`);
        return response.json();
      });
    }
    return manifestPromise;
  }

  function buildTree(paths) {
    const root = {};
    for (const path of paths) {
      const parts = path.split("/");
      let current = root;
      parts.forEach((part, index) => {
        const isFile = index === parts.length - 1;
        if (isFile) {
          current[part] = null;
        } else {
          current[part] ??= {};
          current = current[part];
        }
      });
    }
    return root;
  }

  function sortedEntries(node) {
    return Object.entries(node).sort(([leftName, leftChild], [rightName, rightChild]) => {
      const leftFile = leftChild === null;
      const rightFile = rightChild === null;
      if (leftFile !== rightFile) return leftFile ? 1 : -1;
      return leftName.localeCompare(rightName, undefined, { sensitivity: "base" });
    });
  }

  function renderTreeNode(node, branch, prefix = []) {
    const list = document.createElement("ul");
    list.setAttribute("role", prefix.length ? "group" : "tree");
    if (!prefix.length) list.className = "repository-tree__root";

    for (const [name, child] of sortedEntries(node)) {
      const item = document.createElement("li");
      item.setAttribute("role", "treeitem");
      const pathParts = [...prefix, name];
      if (child === null) {
        item.className = "repository-tree__file";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "repository-file-preview";
        button.dataset.repositoryBranch = branch;
        button.dataset.repositoryPath = pathParts.join("/");
        button.textContent = name;
        item.append(button);
      } else {
        item.className = "repository-tree__directory";
        item.setAttribute("aria-expanded", "true");
        const label = document.createElement("span");
        label.className = "repository-tree__directory-name";
        label.textContent = `${name}/`;
        item.append(label, renderTreeNode(child, branch, pathParts));
      }
      list.append(item);
    }
    return list;
  }

  async function initializeTrees() {
    const containers = [...document.querySelectorAll(".repository-tree[data-repository-branch]")];
    if (!containers.length) return;
    try {
      const manifest = await loadManifest();
      for (const container of containers) {
        const branch = container.dataset.repositoryBranch;
        const files = manifest.branches?.[branch]?.files;
        if (!files) throw new Error(`Tree metadata is unavailable for ${branch}.`);
        const tree = renderTreeNode(buildTree(Object.keys(files)), branch);
        tree.setAttribute("aria-label", `${branch} branch files`);
        container.replaceChildren(tree);
      }
    } catch (error) {
      console.error(error);
      for (const container of containers) {
        const message = document.createElement("p");
        message.className = "repository-tree__error";
        message.textContent = "リポジトリツリーを読み込めませんでした。";
        container.replaceChildren(message);
      }
    }
  }

  const textCache = new Map();
  let lastTrigger = null;

  function formatBytes(value) {
    if (!Number.isFinite(value) || value < 0) return "";
    if (value < 1024) return `${value} B`;
    const units = ["KiB", "MiB", "GiB"];
    let amount = value / 1024;
    let index = 0;
    while (amount >= 1024 && index < units.length - 1) {
      amount /= 1024;
      index += 1;
    }
    return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${units[index]}`;
  }

  function createDialog() {
    const dialog = document.createElement("dialog");
    dialog.className = "repository-preview-dialog";
    dialog.innerHTML = `
      <div class="repository-preview-dialog__panel">
        <header class="repository-preview-dialog__header">
          <div>
            <h2 class="repository-preview-dialog__title"></h2>
            <p class="repository-preview-dialog__meta"></p>
          </div>
          <button type="button" class="repository-preview-dialog__icon-close" aria-label="閉じる">×</button>
        </header>
        <div class="repository-preview-dialog__body">
          <p class="repository-preview-dialog__status" role="status"></p>
          <pre class="repository-preview-dialog__text" hidden><code></code></pre>
          <img class="repository-preview-dialog__image" alt="" hidden>
        </div>
        <footer class="repository-preview-dialog__footer">
          <a class="repository-preview-dialog__github" target="_blank" rel="noopener noreferrer">GitHubで開く</a>
          <button type="button" class="repository-preview-dialog__copy" disabled>コピー</button>
          <button type="button" class="repository-preview-dialog__close">閉じる</button>
        </footer>
      </div>`;
    document.body.append(dialog);

    const close = () => dialog.close();
    dialog.querySelector(".repository-preview-dialog__icon-close").addEventListener("click", close);
    dialog.querySelector(".repository-preview-dialog__close").addEventListener("click", close);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) close();
    });
    dialog.addEventListener("close", () => {
      if (lastTrigger instanceof HTMLElement) lastTrigger.focus();
    });
    return dialog;
  }

  const dialog = createDialog();
  const title = dialog.querySelector(".repository-preview-dialog__title");
  const meta = dialog.querySelector(".repository-preview-dialog__meta");
  const status = dialog.querySelector(".repository-preview-dialog__status");
  const textPanel = dialog.querySelector(".repository-preview-dialog__text");
  const code = textPanel.querySelector("code");
  const image = dialog.querySelector(".repository-preview-dialog__image");
  const githubLink = dialog.querySelector(".repository-preview-dialog__github");
  const copyButton = dialog.querySelector(".repository-preview-dialog__copy");

  function resetPreview() {
    status.textContent = "読み込み中…";
    status.hidden = false;
    textPanel.hidden = true;
    code.textContent = "";
    image.hidden = true;
    image.removeAttribute("src");
    image.alt = "";
    copyButton.disabled = true;
    copyButton.textContent = "コピー";
  }

  async function loadText(url) {
    if (!textCache.has(url)) {
      textCache.set(url, fetch(url).then((response) => {
        if (!response.ok) throw new Error(`File request failed: ${response.status}`);
        return response.text();
      }));
    }
    return textCache.get(url);
  }

  async function showPreview(button) {
    const branch = button.dataset.repositoryBranch;
    const path = button.dataset.repositoryPath;
    if (!branch || !path) return;

    lastTrigger = button;
    resetPreview();
    title.textContent = path;
    meta.textContent = branch;
    githubLink.removeAttribute("href");
    if (!dialog.open) dialog.showModal();

    try {
      const manifest = await loadManifest();
      const branchData = manifest.branches?.[branch];
      const file = branchData?.files?.[path];
      if (!branchData || !file) throw new Error("Preview metadata is unavailable.");

      const shortCommit = branchData.commit.slice(0, 12);
      meta.textContent = `${branch} @ ${shortCommit} · ${formatBytes(file.size)} · ${file.mime_type}`;
      githubLink.href = file.github_url;

      if (file.kind === "text" && file.asset_url) {
        const content = await loadText(file.asset_url);
        code.textContent = content;
        textPanel.hidden = false;
        status.hidden = true;
        copyButton.disabled = false;
        copyButton.onclick = async () => {
          await navigator.clipboard.writeText(content);
          copyButton.textContent = "コピー済み";
          window.setTimeout(() => { copyButton.textContent = "コピー"; }, 1500);
        };
        return;
      }

      if (file.kind === "image" && file.asset_url) {
        image.src = file.asset_url;
        image.alt = `${path} のプレビュー`;
        image.hidden = false;
        status.hidden = true;
        return;
      }

      status.textContent = file.kind === "too-large"
        ? "このファイルはプレビュー上限（512 KiB）を超えています。"
        : "このバイナリ形式はダイアログ内ではプレビューできません。";
    } catch (error) {
      console.error(error);
      status.textContent = "ファイルのプレビューを読み込めませんでした。";
    }
  }

  initializeTrees();

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const button = event.target.closest(".repository-file-preview");
    if (button instanceof HTMLButtonElement) showPreview(button);
  });
})();
