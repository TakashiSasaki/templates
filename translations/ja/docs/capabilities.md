# 再利用可能な capability

> **参考訳（非正本）:** このページは英語正本の参考訳です。内容に差異がある場合は英語正本が優先されます。

これは Composition capability publication のための Site 所有の読者向けインデックスです。このページが定義するのは public navigation だけです。artifact、foundation、capability、runtime、routing、viewport、evidence の canonical semantics は `composition` provider が所有します。

Composition の canonical model は [Composition concepts](/composition/concepts/) を参照してください。browser artifact の選択には provider-owned の [Website と Web application の選び方](/web/) を使用してください。Site はその decision rule をここで再定義しません。

## 公開済み Composition route

### Implementation runtime

- [Implementation runtime decision record](/capabilities/runtime/)
- [Choosing an implementation runtime](/capabilities/runtime/selection/)

### Interfaces

- [Packaged CLI interface](/capabilities/cli/)
- [MCP interface](/capabilities/mcp/)
- [MCP transports](/capabilities/mcp/transports/)
- [MCP Apps interface](/capabilities/mcp-apps/)
- [MCP Apps guidance](/capabilities/mcp-apps/guidance/)
- [Standalone browser interface](/capabilities/browser/)
- [Headless service interface](/capabilities/service/)

### Browser 関連 entry

- [Website と Web application の選び方](/web/)
- [Website](/website/)
- [Web application](/webapp/)
- [Progressive Web App capability](/capabilities/pwa/)

別の [Policy PWA usage guide](/policy/pwa/) は Policy documentation site を install / use するための reader route であり、Composition capability document ではありません。

上記の Composition link はすべて Site publication destination です。正確な provider revision は build artifact の `build-provenance.json` に記録されます。
