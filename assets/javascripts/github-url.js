(function (globalScope, factory) {
  "use strict";
  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  globalScope.TemplatesGithubUrls = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const FULL_SHA = /^[0-9a-f]{40}$/;
  const REPOSITORY = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

  function validate(repository, revision) {
    if (typeof repository !== "string" || !REPOSITORY.test(repository)) {
      throw new TypeError("repository must be owner/name");
    }
    if (typeof revision !== "string" || !FULL_SHA.test(revision)) {
      throw new TypeError("revision must be a lowercase full commit SHA");
    }
  }

  function encodePath(path) {
    if (typeof path !== "string" || path.startsWith("/") || path.includes("\0") || (path && path.split("/").some((part) => ["", ".", ".."].includes(part)))) {
      throw new TypeError("source path must be relative and NUL-free");
    }
    return path.split("/").map((part) => encodeURIComponent(part).replace(/[!'()*]/g, (character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`)).join("/");
  }

  function url(kind, repository, revision, path = "") {
    validate(repository, revision);
    const encoded = encodePath(path);
    return `https://github.com/${repository}/${kind}/${revision}${encoded ? `/${encoded}` : ""}`;
  }

  return Object.freeze({
    commit: (repository, revision) => url("commit", repository, revision),
    blob: (repository, revision, path) => url("blob", repository, revision, path),
    tree: (repository, revision, path = "") => url("tree", repository, revision, path)
  });
});
