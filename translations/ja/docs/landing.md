# Templates ドキュメントポータル

> **参考訳（非正本）:** このページは英語正本の参考訳です。内容に差異がある場合は英語正本が優先されます。

<div class="portal-landing portal-landing--cover">

<section class="portal-cover" aria-labelledby="portal-cover-title">
  <div class="portal-cover__copy">
    <p class="portal-cover__kicker">再利用可能な開発契約</p>
    <h1 id="portal-cover-title">
      合成可能な契約から <span class="portal-accent portal-accent--skill">Agent Skill</span>
      と <span class="portal-accent portal-accent--webapp">Web アプリケーション</span>を構築する
    </h1>
    <p class="portal-cover__lead">
      Composition は Skill / Webapp のアーティファクト意味論と再利用可能な capability を定義します。
      Policy は、検証可能なコーディングエージェントの動作を独立して定義します。
    </p>
    <div class="portal-cover__actions">
      <a class="portal-cover__button portal-cover__button--primary" href="/composition/">
        Composition を見る <span aria-hidden="true">→</span>
      </a>
      <a class="portal-cover__button portal-cover__button--secondary" href="/policy/">
        Policy を見る <span aria-hidden="true">→</span>
      </a>
    </div>
    <ul class="portal-cover__signals" role="list">
      <li>Composition: アーティファクトと capability</li>
      <li>Policy: コーディングエージェントの動作</li>
    </ul>
  </div>

  <div class="portal-cover__visual">
    <img src="/images/landing-architecture.svg" alt="Composition が Agent Skill と Web アプリケーションのアーティファクトを定義し、Policy がコーディングエージェントの動作を独立して定義し、Site が両者を検証済みの一つのポータルとして公開する構成">
  </div>
</section>

<section class="portal-authority" aria-labelledby="portal-build-title">
  <div class="portal-section-heading">
    <p class="portal-section-heading__kicker">Composition</p>
    <h2 id="portal-build-title">何を構築しますか？</h2>
    <p>アーティファクト種別を選択してください。どちらも Composition authority が提供する再利用可能な capability と lifecycle contract を利用します。</p>
  </div>

  <div class="portal-artifact-grid">
    <a class="portal-artifact-card portal-artifact-card--skill" href="/skill/">
      <span class="portal-artifact-card__icon"><img src="/images/icon-skill.svg" alt=""></span>
      <span class="portal-artifact-card__copy">
        <strong>Agent Skill</strong>
        <span>エージェントから起動されるワークフローとリソースの意味論。</span>
      </span>
      <span class="portal-artifact-card__arrow" aria-hidden="true">→</span>
    </a>

    <a class="portal-artifact-card portal-artifact-card--webapp" href="/webapp/">
      <span class="portal-artifact-card__icon"><img src="/images/icon-webapp.svg" alt=""></span>
      <span class="portal-artifact-card__copy">
        <strong>Web アプリケーション</strong>
        <span>ブラウザ製品の route、state、viewport、evidence の意味論。</span>
      </span>
      <span class="portal-artifact-card__arrow" aria-hidden="true">→</span>
    </a>
  </div>
</section>

<section class="portal-policy-panel" aria-labelledby="portal-policy-title">
  <span class="portal-policy-panel__icon"><img src="/images/icon-policy.svg" alt=""></span>
  <div class="portal-policy-panel__copy">
    <p class="portal-policy-panel__label">独立した authority · Policy</p>
    <h2 id="portal-policy-title">コーディングエージェントの動作を定義する</h2>
    <p>共有 operating policy と agent-policy ツールチェーンが、選択、検証、render、adoption、release を扱います。</p>
  </div>
  <a class="portal-policy-panel__action" href="/policy/">Policy を見る <span aria-hidden="true">→</span></a>
</section>

<nav class="portal-doc-nav" aria-labelledby="portal-doc-nav-title">
  <div class="portal-section-heading portal-section-heading--compact">
    <p class="portal-section-heading__kicker">読者向けの導線</p>
    <h2 id="portal-doc-nav-title">ドキュメントを見る</h2>
  </div>
  <div class="portal-doc-links">
    <a class="portal-doc-link" href="/composition/">Composition</a>
    <a class="portal-doc-link" href="/capabilities/">Capabilities</a>
    <a class="portal-doc-link" href="/lifecycle/">Lifecycle</a>
    <a class="portal-doc-link" href="/glossary/">Glossary</a>
    <a class="portal-doc-link" href="/guided/">index.md から探す</a>
    <a class="portal-doc-link" href="/repository-trees/">Repository trees</a>
    <a class="portal-doc-link" href="/files/">Source files</a>
  </div>
</nav>

<section class="portal-guarantees" aria-labelledby="portal-guarantees-title">
  <div class="portal-section-heading portal-section-heading--compact">
    <p class="portal-section-heading__kicker">公開時の保証</p>
    <h2 id="portal-guarantees-title">レビュー済みのソース、再現可能な出力</h2>
  </div>
  <div class="portal-guarantees__grid">
    <article>
      <span class="portal-guarantees__mark" aria-hidden="true">01</span>
      <div><h3>責務ごとに分離</h3><p>Composition、Policy、Site integration には明示的な authority があります。</p></div>
    </article>
    <article>
      <span class="portal-guarantees__mark" aria-hidden="true">02</span>
      <div><h3>整合性のために固定</h3><p>Site はレビュー済みの Composition / Policy revision を full commit SHA で選択します。</p></div>
    </article>
    <article>
      <span class="portal-guarantees__mark" aria-hidden="true">03</span>
      <div><h3>読者向けに検証</h3><p>assembly、navigation、link、provenance、glossary semantics、Pages 出力を検証します。</p></div>
    </article>
  </div>
</section>

</div>
