# Templates ドキュメントポータル

> **参考訳（非正本）:** このページは英語正本の参考訳です。内容に差異がある場合は英語正本が優先されます。

<div class="portal-landing portal-landing--cover">

<section class="portal-cover" aria-labelledby="portal-cover-title">
  <div class="portal-cover__copy">
    <p class="portal-cover__kicker">まず、達成したい作業から選ぶ</p>
    <h1 id="portal-cover-title">
      <span class="portal-accent portal-accent--webapp">Website または Web アプリケーション</span>を作る、
      <span class="portal-accent portal-accent--skill">Agent Skill</span>を作る、
      または coding-agent rules を導入する
    </h1>
    <p class="portal-cover__lead">
      通常、この <code>templates</code> repository 自体を product repository にするのではありません。
      product は別 repository に置き、そこへ目的に合った templates の tooling と contracts を適用します。
    </p>
    <div class="portal-cover__actions">
      <a class="portal-cover__button portal-cover__button--primary" href="/web/">
        Website / Web アプリケーション <span aria-hidden="true">→</span>
      </a>
      <a class="portal-cover__button portal-cover__button--secondary" href="/composition/use/skill-first-use-walkthrough/">
        Agent Skill を作る <span aria-hidden="true">→</span>
      </a>
    </div>
    <ul class="portal-cover__signals" role="list">
      <li>具体的な作業から始め、architecture は必要になってから確認します。</li>
      <li>browser product の選択と shared Web semantics は Composition が所有します。</li>
      <li>Policy は optional で、Composition とは独立しています。</li>
    </ul>
  </div>

  <div class="portal-cover__visual">
    <img src="/images/landing-architecture.svg" alt="Composition が Agent Skill、Website、Web application の artifact を定義し、Policy が coding-agent operation を独立して定義し、Site が両 authority を検証済みの一つのポータルとして公開する構成">
  </div>
</section>

<section class="portal-authority" aria-labelledby="portal-build-title">
  <div class="portal-section-heading">
    <p class="portal-section-heading__kicker">何をしたいですか？</p>
    <h2 id="portal-build-title">内部 authority ではなく task を選ぶ</h2>
    <p>各 entry point は、その手順を正本として所有する authority へ案内します。開始前に Composition、capability、lifecycle contract を理解する必要はありません。まず対話的に resolved output を試したい場合は、<a href="/playground/">Composition Playground を試す</a>ことができます。</p>
  </div>

  <div class="portal-artifact-grid">
    <a class="portal-artifact-card portal-artifact-card--webapp" href="/web/">
      <span class="portal-artifact-card__icon"><img src="/images/icon-web.svg" alt=""></span>
      <span class="portal-artifact-card__copy">
        <strong>Website か Web アプリケーションかを選ぶ</strong>
        <span>Composition の canonical selector に従い、その後で公開済みの Website または Web application walkthrough へ進みます。</span>
      </span>
      <span class="portal-artifact-card__arrow" aria-hidden="true">→</span>
    </a>

    <a class="portal-artifact-card portal-artifact-card--skill" href="/composition/use/skill-first-use-walkthrough/">
      <span class="portal-artifact-card__icon"><img src="/images/icon-skill.svg" alt=""></span>
      <span class="portal-artifact-card__copy">
        <strong>Agent Skill を作る</strong>
        <span>Release Note Helper walkthrough を、別 consumer repository の作成から concrete な knowledge-augmented Skill と behavioral evaluation まで順に進めます。</span>
      </span>
      <span class="portal-artifact-card__arrow" aria-hidden="true">→</span>
    </a>
  </div>
</section>

<section class="portal-policy-panel" aria-labelledby="portal-policy-title">
  <span class="portal-policy-panel__icon"><img src="/images/icon-policy.svg" alt=""></span>
  <div class="portal-policy-panel__copy">
    <p class="portal-policy-panel__label">独立した task · Policy</p>
    <h2 id="portal-policy-title">repository に coding-agent rules を追加する</h2>
    <p>新規導入または既存 agent instructions の migration は Policy getting-started から始めます。Policy は独立した authority であり、Composition capability ではありません。</p>
  </div>
  <a class="portal-policy-panel__action" href="/policy/getting-started/">Policy adoption を始める <span aria-hidden="true">→</span></a>
</section>

<section class="portal-authority" aria-labelledby="portal-repository-model-title">
  <div class="portal-section-heading portal-section-heading--compact">
    <p class="portal-section-heading__kicker">Mental model</p>
    <h2 id="portal-repository-model-title">作業するのは product repository</h2>
    <p>通常の関係は次のとおりです。</p>
  </div>

```text
TakashiSasaki/templates
        |
        | tooling と contracts を提供
        v
あなたの別 product repository
```

<p>product repository は別に clone または作成します。provider-owned tutorial が、そこで何を install / run するかを説明します。<code>templates</code> repository 自体は主に tooling、contracts、documentation の供給元です。</p>
</section>

<section class="portal-policy-panel" aria-labelledby="portal-reference-consumer-title">
  <span class="portal-policy-panel__icon"><img src="/images/icon-policy.svg" alt=""></span>
  <div class="portal-policy-panel__copy">
    <p class="portal-policy-panel__label">具体例 · Self-hosting</p>
    <h2 id="portal-reference-consumer-title">この repository 自身が自分の仕組みを使う例を見る</h2>
    <p><code>TakashiSasaki/templates</code> 自身も実行可能な reference consumer です。Composition が Site の Website/PWA product を定義し、Policy が Site maintenance を規定して、保守に使う agent/review instructions を生成します。この関係は特別な統合 authority にはせず、独立した consumer state のまま維持します。</p>
  </div>
  <a class="portal-policy-panel__action" href="/coexistence/#self-hosting-reference-consumer">Reference consumer を見る <span aria-hidden="true">→</span></a>
</section>

<nav class="portal-doc-nav" aria-labelledby="portal-doc-nav-title">
  <div class="portal-section-heading portal-section-heading--compact">
    <p class="portal-section-heading__kicker">すでに始めている、または仕組みを知りたい</p>
    <h2 id="portal-doc-nav-title">Architecture と reference を見る</h2>
  </div>
  <div class="portal-doc-links">
    <a class="portal-doc-link" href="/composition/">Composition を見る</a>
    <a class="portal-doc-link" href="/playground/">Composition Playground を試す</a>
    <a class="portal-doc-link" href="/composition/concepts/">Composition の概念と用語</a>
    <a class="portal-doc-link" href="/web/">Website か Web application か</a>
    <a class="portal-doc-link" href="/website/">Website を見る</a>
    <a class="portal-doc-link" href="/webapp/">Web application を見る</a>
    <a class="portal-doc-link" href="/skill/">Agent Skill を見る</a>
    <a class="portal-doc-link" href="/policy/">Policy を見る</a>
    <a class="portal-doc-link" href="/coexistence/#self-hosting-reference-consumer">この repository を reference consumer として見る</a>
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