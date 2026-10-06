/** Directory tree view: folder paths listed in depth order, each level of
 *  subfolders indented one step. Clicking a row scopes every metric to that
 *  directory (same behaviour as clicking a treemap cell). */
import { fmtInt, fmtSigned, relPathName } from "../lib/format";
import type { DirRow } from "../types";

export function DirectoryTree({
  items,
  scope,
  currentPath,
  onScope,
}: {
  items: DirRow[];
  scope: string;
  currentPath: string;
  onScope: (path: string) => void;
}) {
  const scopeDepth = items.find((i) => i.path === scope)?.depth ?? 0;
  return (
    <div className="tree">
      <div className="tree-head">
        <span>Directory</span>
        <span className="num">Churn</span>
        <span className="num">Growth</span>
        <span className="num">Mods</span>
      </div>
      {items.map((it) => {
        const rel = Math.max(0, it.depth - scopeDepth);
        const isCurrent = it.path === currentPath;
        const label = it.path ? relPathName(it.path, scope) : "/ (repository root)";
        return (
          <div
            key={it.path || "/"}
            className={`tree-row${isCurrent ? " current" : ""}`}
            title={`/${it.path}${it.path ? "/" : ""} — click to scope every metric here`}
            onClick={() => {
              if (!isCurrent) onScope(it.path);
            }}
          >
            <span className="name" style={{ paddingLeft: rel * 18 }}>
              {label}
              {it.path !== "" && <span className="faint">/</span>}
            </span>
            <span className="num">{fmtInt(it.churn)}</span>
            <span className={`num ${it.growth >= 0 ? "pos" : "neg"}`}>
              {fmtSigned(it.growth)}
            </span>
            <span className="num">{fmtInt(it.modifications)}</span>
          </div>
        );
      })}
    </div>
  );
}
