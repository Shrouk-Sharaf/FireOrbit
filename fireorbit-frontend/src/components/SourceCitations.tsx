import { useState } from 'react';
import type { Source } from '../types';
import { ChevronIcon, FileIcon } from './Icons';

interface SourceItemProps {
  source: Source;
  index: number;
  defaultOpen: boolean;
}

function SourceItem({ source, index, defaultOpen }: SourceItemProps) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = `source-${source.chunk_id}-${index}`;
  return (
    <li className="source">
      <button
        type="button"
        className="source__header"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
      >
        <FileIcon size={16} className="source__file" />
        <span className="source__doc" title={source.document}>
          {source.document}
        </span>
        <span className="chip">{source.page != null ? `Page ${source.page}` : 'Page n/a'}</span>
        <span className="chip chip--mono">{source.chunk_id}</span>
        {source.is_mock && <span className="chip chip--mock">Mock</span>}
        <ChevronIcon size={16} className={`chevron ${open ? 'chevron--open' : ''}`} />
      </button>
      {open && (
        <blockquote id={panelId} className="source__passage">
          {source.content || 'No passage text was returned for this source.'}
        </blockquote>
      )}
    </li>
  );
}

interface Props {
  sources: Source[];
  defaultOpen: boolean;
}

export function SourceCitations({ sources, defaultOpen }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  if (sources.length === 0) return null;
  const mock = sources.some((s) => s.is_mock);
  return (
    <section className="sources" aria-label="Sources">
      <button
        type="button"
        className="sources__toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <ChevronIcon size={16} className={`chevron ${open ? 'chevron--open' : ''}`} />
        {sources.length} {sources.length === 1 ? 'source' : 'sources'}
        {mock && <span className="chip chip--mock">Mock sources</span>}
      </button>
      {open && (
        <ul className="sources__list">
          {sources.map((s, i) => (
            <SourceItem key={`${s.chunk_id}-${i}`} source={s} index={i} defaultOpen={defaultOpen} />
          ))}
        </ul>
      )}
    </section>
  );
}
