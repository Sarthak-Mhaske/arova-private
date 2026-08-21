import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { surfaceIn, easeSoft } from '../../motion';
import { SurfacingItem, useCognitionState, useSurfaceState } from '../../state';
import { ActionChip } from './ActionChip';
import { socket } from '../../runtime/socket';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const formatMarkdownText = (text: string): string => {
  if (!text) return '';

  let normalized = text
    .replace(/[\u202f\xa0]/g, ' ')
    .replace(/[\u2011]/g, '-');

  // 1. Auto-close unclosed code block fences (odd number of ```) so streaming code is NEVER mangled by prose regexes
  const backticks = (normalized.match(/```/g) || []).length;
  if (backticks % 2 !== 0) {
    normalized = normalized + '\n```';
  }

  // 2. Split safely by code block fences (```...```)
  const parts = normalized.split(/(```[\s\S]*?```)/g);

  return parts.map((part) => {
    if (part.startsWith('```')) {
      const matchFence = part.match(/^```([a-zA-Z0-9_+-]*)\s*\n?([\s\S]*?)```$/);
      if (matchFence) {
        let lang = matchFence[1].trim() || 'code';
        let rawCode = matchFence[2] || '';
        return `\n\n\`\`\`${lang}\n${rawCode.trim()}\n\`\`\`\n\n`;
      }
      return part;
    }

    let formatted = part;

    // A. Normalize LaTeX Math blocks:
    // 1) Clean up single isolated dollar signs on their own lines (e.g. "$\n\n...\n\n$")
    formatted = formatted.replace(/(?:^|\n)\s*\$\s*\n+([\s\S]*?)\n+\s*\$\s*(?:\n|$)/g, (_, m) => `\n\n$$\n${m.trim()}\n$$\n\n`);
    // 2) Handle \[ ... \] display math
    formatted = formatted.replace(/\\\[([\s\S]*?)\\\]/g, (_, m) => `\n\n$$\n${m.trim()}\n$$\n\n`);
    // 3) Handle \( ... \) inline math
    formatted = formatted.replace(/\\\(([\s\S]*?)\\\)/g, (_, m) => `$${m.trim()}$`);
    // 4) Handle bare bracket math like [ \text{Position} = N \times \frac{n}{q} ]
    formatted = formatted.replace(/\[\s*([\s\S]*?\\(?:frac|text|times|sum|int|sqrt)\{[\s\S]*?|[\s\S]*?\\times[\s\S]*?)\s*\]/g, (_, m) => `\n\n$$\n${m.trim()}\n$$\n\n`);
    // 5) Clean double-wrapped $$ if any occurred
    formatted = formatted.replace(/\$\$\s*\n*\$\$/g, '$$');

    // B. Clean angle brackets, malformed markdown links, and trailing html artifacts from URLs
    formatted = formatted.replace(/<+\s*(\[[^\]]+\]\([^\)]+\))\.?\s*(?:html>?)?/gi, '$1');
    formatted = formatted.replace(/<+\s*(https?:\/\/[^\s>]+)>+\.?\s*(?:html>?)?/gi, '$1');
    formatted = formatted.replace(/(https?:\/\/[^\s<>)"\]]+)\.html>/gi, '$1');
    formatted = formatted.replace(/\]\((https?:\/\/[^\s)]+)\.\s*html[|>]*\)/gi, ']($1)');
    formatted = formatted.replace(/\]\((https?:\/\/[^\s)]+)\)\.?\s*(?:html>?)?/gi, ']($1)');

    // C. Clean HTML <br> tags in table cells or text into clean inline bullet marks
    formatted = formatted.replace(/<br\s*\/?>\s*[*•-]?\s*/gi, ' • ');

    // D. Separate title from attached tables: e.g. "Title 2026| Aspect | Details |" -> "Title 2026\n\n| Aspect | Details |"
    formatted = formatted.replace(/([^\n|])\s*(\|[^|\n]+\|[^|\n]+\|)/g, '$1\n\n$2');

    // E. Reconstruct collapsed single-line or broken tables into valid GFM tables
    formatted = formatted.replace(/(?:^|\n)(\|[^|\n]+(?:\|[^|\n]+)+\|[\s\S]*?\|[-: ]+\|[\s\S]*?\|)(?=\s*(?:\n\s*[A-Za-z0-9#*]|\bBottom\s*line\b|$))/gi, (match, tableBlock) => {
      const rawCells = tableBlock.split('|').map((c: string) => c.trim());
      const isDelimiter = (s: string) => /^[\s\-:|]+$/.test(s) && s.includes('--');

      const nonEmpties = rawCells.filter((c: string) => c.length > 0);
      if (nonEmpties.length < 4) return match;

      const headers: string[] = [];
      let delimStart = -1;
      for (let i = 0; i < nonEmpties.length; i++) {
        if (isDelimiter(nonEmpties[i])) {
          delimStart = i;
          break;
        } else {
          headers.push(nonEmpties[i]);
        }
      }

      if (headers.length === 0 || delimStart === -1) return match;

      const numCols = headers.length;
      const dataTokens: string[] = [];
      for (let i = delimStart; i < nonEmpties.length; i++) {
        if (!isDelimiter(nonEmpties[i])) {
          dataTokens.push(nonEmpties[i]);
        }
      }

      const rows: string[] = [];
      rows.push('| ' + headers.join(' | ') + ' |');
      rows.push('| ' + Array(numCols).fill('---').join(' | ') + ' |');

      for (let i = 0; i < dataTokens.length; i += numCols) {
        const row = dataTokens.slice(i, i + numCols);
        while (row.length < numCols) row.push('');
        rows.push('| ' + row.join(' | ') + ' |');
      }

      return '\n\n' + rows.join('\n') + '\n\n';
    });

    // F. Fix horizontal rules attached to text - EXCLUDE table delimiters (| --- |)
    formatted = formatted.replace(/^([^\n|]+?)\s*(---|___|\*\*\*)\s*$/gm, (m, text, hr) => {
      if (text.includes('|')) return m;
      return `${text.trim()}\n\n${hr}\n`;
    });
    formatted = formatted.replace(/([^\n|\s])\s*(---|___|\*\*\*)\s*(?=[^\n|\s])/g, (m, prefix, hr) => {
      if (prefix === '|') return m;
      return `${prefix}\n\n${hr}\n\n`;
    });

    // G. Fix numbered lists and headings (e.g. "2.Common Sources" -> "2. Common Sources")
    formatted = formatted.replace(/(\d+)\.([A-Za-z])/g, '$1. $2');
    formatted = formatted.replace(/([^\n])\s*(\d+)\.\s+([A-Z])/g, '$1\n\n$2. $3');

    // H. Fix inline bullet list asterisks ONLY outside of tables
    const rawLines = formatted.split('\n');
    const tableSafeLines = rawLines.map(line => {
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        return line;
      }
      return line.replace(/([:.;?!])\s*([*•-])(?=\s+[A-Za-z0-9_`"'(\[])/g, '$1\n\n* ');
    });
    formatted = tableSafeLines.join('\n');

    // I. Fix headers glued to previous sentence (e.g. "text.# Header" -> "text.\n\n# Header")
    formatted = formatted.replace(/([^\n])\s*(#{1,6})\s+([A-Za-z0-9])/g, '$1\n\n$2 $3');

    // J. Fix punctuation glued directly to uppercase words
    formatted = formatted.replace(/([a-z0-9])([.!?])([A-Z])/g, '$1$2 $3');

    // K. Fix "Bottom line..." glued words
    formatted = formatted.replace(/\bBottom line([A-Za-z])/g, 'Bottom line: $1');
    formatted = formatted.replace(/([^\n])\s*(\bBottom line\b)/g, '$1\n\n**$2**');

    // L. Fix small-LLM glued words
    const gluedPairs = [
      ['open', 'with'], ['open', 'in'], ['open', 'no'],
      ['these', 'is'], ['this', 'is'], ['exact', 'error'],
      ['any', 'red'], ['console', 'output'], ['but', 'sometimes'],
      ['can', 'you'], ['show', 'me'], ['there', 'are'],
      ['which', 'of'], ['paste', 'the'], ['below', 'is'],
      ['status', 'bar'], ['error', 'markers'], ['execution', 'output'],
      ['still', 'seeing'], ['who', 'is'], ['that', 'are'], ['which', 'are'],
      ['is', 'expected'], ['are', 'expected'], ['is', 'scheduled'],
      ['is', 'serving'], ['is', 'meant'], ['has', 'announced'],
      ['need', 'to'], ['plan', 'to'], ['schools', 'to'], ['remain', 'closed'],
      ['political', 'and'], ['markets', 'and'], ['weddings', 'and'],
      ['water', 'supply'], ['medical', 'stores'], ['though', 'passengers'],
      ['especially', 'on'], ['expressed', 'support'], ['services', 'are'],
      ['outside', 'the'], ['other', 'essential'], ['and', 'other'],
      ['and', 'most'], ['is', 'reportedly'], ['the', 'group'], ['who', 'is']
    ];
    for (const [w1, w2] of gluedPairs) {
      const reg = new RegExp(`\\b${w1}${w2}\\b`, 'gi');
      formatted = formatted.replace(reg, `${w1} ${w2}`);
    }

    // M. Fix unclosed bold asterisks across paragraphs
    const paragraphs = formatted.split(/\n\n+/);
    const cleanedParagraphs = paragraphs.map(p => {
      let pClean = p.trim();
      const boldMatches = pClean.match(/\*\*/g) || [];
      if (boldMatches.length % 2 !== 0) {
        if (pClean.startsWith('**')) {
          pClean = pClean.slice(2).trim();
        } else if (pClean.endsWith('**')) {
          pClean = pClean.slice(0, -2).trim();
        } else {
          pClean = pClean.replace(/\*\*/, '');
        }
      }
      return pClean;
    });

    return cleanedParagraphs.join('\n\n');
  }).join('');
};

const getCleanLinkLabel = (children: React.ReactNode, href?: string): string => {
  let rawText = '';
  if (typeof children === 'string') {
    rawText = children;
  } else if (Array.isArray(children)) {
    rawText = children.map(c => {
      if (typeof c === 'string') return c;
      if (c && typeof c === 'object' && 'props' in c && c.props.children) {
        return typeof c.props.children === 'string' ? c.props.children : '';
      }
      return '';
    }).join('');
  }
  
  let target = (rawText || '').trim() || href || '';
  target = target.replace(/^[<(\[]+/, '').replace(/[>)\].|\s]+$/, '').trim();
  
  if (/^https?:\/\//i.test(target) || /^www\./i.test(target) || /^[a-z0-9-]+(\.[a-z0-9-]+)+/i.test(target)) {
    try {
      const cleanUrl = target.replace(/^[<(\[]+/, '').replace(/[>)\].|\s]+$/, '').replace(/\s+/g, '');
      const parsed = new URL(cleanUrl.startsWith('http') ? cleanUrl : `https://${cleanUrl}`);
      let host = parsed.hostname.replace(/^www\./, '');
      if (host) return host;
    } catch {
      const m = target.match(/(?:https?:\/\/)?(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i);
      if (m && m[1]) return m[1].replace(/\s+/g, '');
    }
  }

  return rawText || href || 'Source';
};

const CopyCodeButton: React.FC<{ code: string }> = ({ code }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      style={{
        background: copied ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.06)',
        border: `1px solid ${copied ? 'rgba(16, 185, 129, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
        borderRadius: '6px',
        color: copied ? '#10b981' : 'var(--ink-2)',
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        fontSize: '11px',
        fontWeight: 500,
        padding: '3px 9px',
        transition: 'all 0.2s ease',
        textTransform: 'none',
        letterSpacing: 'normal',
        whiteSpace: 'nowrap',
        flexShrink: 0
      }}
      title="Copy code to clipboard"
    >
      {copied ? (
        <>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>Copied!</span>
        </>
      ) : (
        <>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          <span>Copy</span>
        </>
      )}
    </button>
  );
};

export const Surfacing: React.FC<{ item: SurfacingItem }> = ({ item }) => {
  const { removeItems, lastExecutionMetadata } = useCognitionState();
  const { openSurface } = useSurfaceState();
  const [showMeta, setShowMeta] = React.useState(false);
  const [showAdvanced, setShowAdvanced] = React.useState(false);
  const metaRef = React.useRef<HTMLDivElement>(null);

  const meta = (item as any).execution_metadata || lastExecutionMetadata;

  React.useEffect(() => {
    if (!showMeta) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (metaRef.current && !metaRef.current.contains(e.target as Node)) {
        setShowMeta(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowMeta(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [showMeta]);

  const handleAction = (act: NonNullable<SurfacingItem['actions']>[0]) => {
    if (act.eventType) {
      window.dispatchEvent(new CustomEvent('arova-send', { 
        detail: { type: act.eventType, ...(act.eventPayload || {}) } 
      }));
    }
    
    if (act.clientAction === 'open_timeline') {
      openSurface('timeline');
    }
    
    // Always dismiss the surfacing item if it was interacted with
    if (item.kind === 'momentum') {
      removeItems([item.id]);
    }
  };

  return (
    <MDiv 
      className={`surfacing ${item.kind ? item.kind : ''}`}
      variants={surfaceIn}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: 0.9, ease: easeSoft.ease }}
    >
      <div className="from">{item.from}</div>
      {item.lede && <div className="lede">{item.lede}</div>}
      {item.paragraphs.map((p, i) => (
        <div key={i} style={{ wordBreak: 'break-word' }}>
          <ReactMarkdown 
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              h1({ children }) {
                return <h1 style={{ fontSize: '22px', fontWeight: 600, marginTop: '28px', marginBottom: '12px', color: 'var(--ink-1)', letterSpacing: '-0.015em' }}>{children}</h1>;
              },

              h2({ children }) {
                return <h2 style={{ fontSize: '18px', fontWeight: 600, marginTop: '24px', marginBottom: '10px', color: 'var(--ink-1)', letterSpacing: '-0.01em' }}>{children}</h2>;
              },
              h3({ children }) {
                return <h3 style={{ fontSize: '15.5px', fontWeight: 600, marginTop: '20px', marginBottom: '8px', color: 'var(--ink-1)' }}>{children}</h3>;
              },
              h4({ children }) {
                return <h4 style={{ fontSize: '14px', fontWeight: 600, marginTop: '16px', marginBottom: '6px', color: 'var(--ink-1)' }}>{children}</h4>;
              },
              hr() {
                return <hr style={{ border: 'none', borderTop: '1px solid var(--hairline-2)', margin: '24px 0' }} />;
              },
              a({ href, children }) {
                const handleClick = (e: React.MouseEvent) => {
                  e.preventDefault();
                  if (!href) return;
                  socket.sendEvent({
                    type: 'user.message',
                    text: `open ${href}`,
                    vocalize: false
                  });
                };
                const label = getCleanLinkLabel(children, href);
                return (
                  <a 
                    href={href} 
                    onClick={handleClick}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="surfacing-link-pill"
                    title={href}
                  >
                    <span className="link-icon">↗</span>
                    <span className="link-label">{label}</span>
                  </a>
                );
              },
              p({ children }) {
                return <p style={{ marginBottom: '14px', lineHeight: '1.7', color: 'var(--ink-2)', fontSize: '15px' }}>{children}</p>;
              },
              ol({ children }) {
                return <ol style={{ paddingLeft: '22px', marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>{children}</ol>;
              },
              ul({ children }) {
                return <ul style={{ paddingLeft: '22px', marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>{children}</ul>;
              },
              li({ children }) {
                return <li style={{ color: 'var(--ink-2)', lineHeight: '1.65', fontSize: '14.5px' }}>{children}</li>;
              },
              strong({ children }) {
                return <strong style={{ color: 'var(--ink-1)', fontWeight: 600 }}>{children}</strong>;
              },
              table({ children }) {
                return (
                  <div style={{ width: '100%', overflowX: 'auto', margin: '20px 0', borderRadius: '10px', border: '1px solid var(--hairline-2)', background: 'var(--glass-1)' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13.5px', lineHeight: '1.6' }}>
                      {children}
                    </table>
                  </div>
                );
              },
              thead({ children }) {
                return <thead style={{ background: 'rgba(255, 255, 255, 0.05)', borderBottom: '1px solid var(--hairline-2)' }}>{children}</thead>;
              },
              tbody({ children }) {
                return <tbody>{children}</tbody>;
              },
              tr({ children }) {
                return <tr style={{ borderBottom: '1px solid var(--hairline-2)' }}>{children}</tr>;
              },
              th({ children }) {
                return <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--ink-1)', fontSize: '13px', letterSpacing: '0.01em' }}>{children}</th>;
              },
              td({ children }) {
                return <td style={{ padding: '10px 14px', color: 'var(--ink-2)', fontSize: '13.5px', verticalAlign: 'top' }}>{children}</td>;
              },
              code({ node, inline, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '');
                const codeText = String(children).replace(/\n$/, '');
                const isMultiline = !inline && (match || codeText.includes('\n') || codeText.includes('def ') || codeText.includes('class ') || codeText.includes('SELECT '));
                
                if (isMultiline) {
                  const lang = match ? match[1] : 'code';
                  return (
                    <div style={{ margin: '18px 0', background: 'rgba(14, 12, 18, 0.95)', border: '1px solid var(--hairline-2)', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}>
                      <div style={{ padding: '8px 16px', background: 'rgba(255,255,255,0.04)', borderBottom: '1px solid var(--hairline-2)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: '#d4a878', fontFamily: 'monospace', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.1em' }}>
                        <span style={{ whiteSpace: 'nowrap', flexShrink: 0 }}>{lang}</span>
                        <CopyCodeButton code={codeText} />
                      </div>
                      <pre style={{ padding: '18px 22px', margin: 0, overflowX: 'hidden', fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace", fontSize: '13.5px', lineHeight: '1.65', color: '#e8d0a4', whiteSpace: 'pre-wrap', wordBreak: 'break-word', background: 'transparent' }}>
                        <code style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{codeText}</code>
                      </pre>
                    </div>
                  );
                }
                return (
                  <code style={{ background: 'rgba(255,255,255,0.08)', padding: '2px 6px', borderRadius: '4px', fontFamily: 'monospace', fontSize: '13px', color: '#d4a878' }} {...props}>
                    {children}
                  </code>
                );
              }
            }}
          >
            {formatMarkdownText(p)}
          </ReactMarkdown>
        </div>
      ))}

      {item.actions && item.actions.length > 0 && (
        <div className="actions-inline">
          {item.actions.map((act, i) => (
            <ActionChip key={i} primary={act.primary} onClick={() => handleAction(act)}>
              {act.primary && (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
              )}
              {act.label}
            </ActionChip>
          ))}
        </div>
      )}

      {/* AI Trust Badge & Metadata */}
      {meta && meta.model_name && (
        <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--hairline-2)', fontSize: '12px' }}>
          <button 
            style={{ 
              background: 'none', 
              border: 'none', 
              color: meta.fallback ? '#ff9800' : 'var(--ink-3)', 
              cursor: 'pointer', 
              display: 'inline-flex', 
              alignItems: 'center', 
              gap: '6px', 
              fontSize: '12px', 
              padding: 0 
            }}
            onClick={() => setShowMeta(!showMeta)}
          >
            {meta.fallback ? (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            )}
            <span style={{ fontWeight: 500 }}>
              {meta.fallback 
                ? `Fallback: ${meta.requested_model || 'Preferred AI'} → ${meta.model_name}` 
                : `${meta.model_name}`}
            </span>
            <span style={{ opacity: 0.6 }}>· {meta.latency_ms ? (meta.latency_ms / 1000).toFixed(1) + 's' : 'Fast'}</span>
          </button>

          {showMeta && (
            <div ref={metaRef} style={{ marginTop: '10px', padding: '12px 14px', background: 'var(--glass-1)', border: '1px solid var(--hairline-2)', borderRadius: '8px', color: 'var(--ink)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: 'var(--ink-3)' }}>Generated with</span>
                <strong>{meta.model_name}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: 'var(--ink-3)' }}>Latency</span>
                <strong>{meta.latency_ms ? (meta.latency_ms / 1000).toFixed(2) + ' s' : 'Instant'}</strong>
              </div>

              {meta.fallback && (
                <div style={{ marginTop: '8px', padding: '8px 10px', background: 'rgba(255, 152, 0, 0.1)', border: '1px solid rgba(255, 152, 0, 0.3)', borderRadius: '6px', fontSize: '11px', color: '#ffa726' }}>
                  <strong>Why wasn't this model used?</strong>
                  <div style={{ marginTop: '2px' }}>{meta.fallback_reason || 'Preferred model was unconfigured, offline, or rate-limited. Fallback is enabled.'}</div>
                </div>
              )}

              <button 
                style={{ background: 'none', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', fontSize: '11px', marginTop: '8px', padding: 0, textDecoration: 'underline' }}
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                {showAdvanced ? 'Hide Advanced ▲' : 'Advanced ▼'}
              </button>

              {showAdvanced && (
                <div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--ink-3)', borderTop: '1px dashed var(--hairline-2)', paddingTop: '6px', lineHeight: '1.6' }}>
                  <div>Provider ID: {meta.provider_id || 'internal'}</div>
                  <div>Requested Model: {meta.requested_model || meta.model_name}</div>
                  <div>Fallback Active: {meta.fallback ? 'Yes' : 'No'}</div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </MDiv>
  );
};
