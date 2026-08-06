import React from 'react';
import { motion } from 'framer-motion';
const MDiv: any = motion.div;
import { surfaceIn, easeSoft } from '../../motion';
import { SurfacingItem, useCognitionState, useSurfaceState } from '../../state';
import { ActionChip } from './ActionChip';
import { socket } from '../../runtime/socket';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const formatMarkdownText = (text: string): string => {
  if (!text) return '';

  let normalized = text;

  // 1. Auto-close unclosed code block fences (odd number of ```) so streaming code is NEVER mangled by prose regexes
  const backticks = (normalized.match(/```/g) || []).length;
  if (backticks % 2 !== 0) {
    normalized = normalized + '\n```';
  }

  // 2. Split safely by code block fences (```...```)
  const parts = normalized.split(/(```[\s\S]*?```)/g);

  return parts.map((part) => {
    if (part.startsWith('```')) {
      // It's a code block! Extract language and body
      let cleaned = part.replace(/^```([a-zA-Z0-9_-]+)?([^\n\s])/g, '```$1\n$2');
      const inner = cleaned.slice(3, -3); // Strip ``` boundaries
      const firstLineBreak = inner.indexOf('\n');
      
      let lang = 'python';
      let rawCode = inner;

      if (firstLineBreak !== -1) {
        const potentialLang = inner.slice(0, firstLineBreak).trim();
        if (potentialLang && !potentialLang.includes(' ') && potentialLang.length < 20) {
          lang = potentialLang;
          rawCode = inner.slice(firstLineBreak + 1);
        }
      }

      // If code statement keywords were concatenated on a single line, format into multiline
      if (!rawCode.includes('\n')) {
        rawCode = rawCode
          .replace(/(import\s+[a-zA-Z0-9_]+)(import|from|class|def)/g, '$1\n$2')
          .replace(/(class\s+[a-zA-Z0-9_]+:)(def|import)/g, '$1\n  $2')
          .replace(/(def\s+[a-zA-Z0-9_]+\([^)]*\):)([a-zA-Z0-9_.]+=|self\.)/g, '$1\n    $2')
          .replace(/(self\.[a-zA-Z0-9_.]+\([^)]*\))(def|self\.)/g, '$1\n    $2');
      }

      return `\n\n\`\`\`${lang}\n${rawCode.trim()}\n\`\`\`\n\n`;
    }

    // For non-code prose text:
    let formatted = part;

    // Clean up orphan bold asterisks around URLs & absolute file paths
    formatted = formatted.replace(/\*\*\s*(https?:\/\/[^\s]+)/g, '$1');
    formatted = formatted.replace(/(https?:\/\/[^\s*]+)\s*\*\*/g, '$1');
    formatted = formatted.replace(/\*\*\s*(\/[a-zA-Z0-9_.~/-]+|\~\/[a-zA-Z0-9_.~/-]+)/g, '$1');
    formatted = formatted.replace(/(\/[a-zA-Z0-9_.~/-]+|\~\/[a-zA-Z0-9_.~/-]+)\s*\*\*/g, '$1');

    // Fix LLM quirk where opening bold ** is placed before a newline (e.g. "text.**\n\nTitle**:")
    formatted = formatted.replace(/\*\*\s*\n+\s*([a-zA-Z0-9\[])/g, '\n\n**$1');

    // Process paragraph by paragraph to guarantee ** never leaks across double newlines
    const paragraphs = formatted.split(/\n\n+/);
    const cleanedParagraphs = paragraphs.map(p => {
      let pClean = p.trim();
      const boldCount = (pClean.match(/\*\*/g) || []).length;
      if (boldCount % 2 !== 0) {
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

    formatted = cleanedParagraphs.join('\n\n');

    // Fix missing newlines before list items ("factors:1.**Data Modeling**" -> "factors:\n\n1. **Data Modeling**")
    formatted = formatted.replace(/([^\n])(\d+)\.\s*(\*{0,2}|_{0,2}|`{0,3})([A-Za-z0-9])/g, '$1\n\n$2. $3$4');

    // Fix period followed directly by Capital letter ("down.To" -> "down. To") without breaking URLs
    formatted = formatted.replace(/([a-z0-9]{3,})\.([A-Z][a-z])/g, '$1. $2');

    return formatted;
  }).join('');
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
        letterSpacing: 'normal'
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
            remarkPlugins={[remarkGfm]}
            components={{
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
                return (
                  <a 
                    href={href} 
                    onClick={handleClick}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#60a5fa', textDecoration: 'underline', cursor: 'pointer' }}
                  >
                    {children}
                  </a>
                );
              },
              p({ children }) {
                return <p style={{ marginBottom: '14px', lineHeight: '1.65', color: 'var(--ink-2)' }}>{children}</p>;
              },
              ol({ children }) {
                return <ol style={{ marginLeft: '24px', marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>{children}</ol>;
              },
              ul({ children }) {
                return <ul style={{ marginLeft: '24px', marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>{children}</ul>;
              },
              li({ children }) {
                return <li style={{ color: 'var(--ink-2)', lineHeight: '1.6' }}>{children}</li>;
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
                        <span>{lang}</span>
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
            <span>{meta.fallback ? '⚠' : '⚡'}</span>
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
