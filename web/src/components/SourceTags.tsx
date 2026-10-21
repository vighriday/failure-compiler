import { Fragment } from "react";
import type { SourceTag } from "../types";

export function focusedSourceLine() {
  return document.activeElement?.closest<HTMLElement>("[data-source-line]")?.dataset.sourceLine;
}

export function sourceTagLabel(tag: SourceTag) {
  return tag.kind === "mention"
    ? `${tag.label} · mentioned on ${tag.source_line}`
    : `${tag.label} · ${tag.source_line}`;
}

export default function SourceTags({tags, onHighlight}: {
  tags?: SourceTag[];
  onHighlight?: (line: string | undefined) => void;
}) {
  if (!tags?.length) return <span className={onHighlight ? "source-tag" : undefined}>No source line</span>;
  return <span className="source-tags">{tags.map((tag, index) => <Fragment key={`${tag.kind}:${tag.label}:${tag.source_line}:${index}`}>
    {index > 0 && " · "}
    {onHighlight
      ? <button type="button" className="source-tag" data-source-line={tag.source_line} onMouseMove={(event) => { event.stopPropagation(); onHighlight(tag.source_line); }} onMouseLeave={() => onHighlight(focusedSourceLine())} onFocus={() => onHighlight(tag.source_line)} onBlur={() => onHighlight(undefined)} onClick={() => onHighlight(tag.source_line)}>{sourceTagLabel(tag)}</button>
      : <span>{sourceTagLabel(tag)}</span>}
  </Fragment>)}</span>;
}
