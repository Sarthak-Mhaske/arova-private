import React, { useMemo, useState, useRef, useCallback, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { InfoRow, ActionButton, EmptyState } from '../ui/CoherenceComponents';

// A wrapper to handle the side panel and force graph
interface MemoryGraphViewProps {
  memories: any[];
  onPinToggle: (id: string, currentlyPinned: boolean) => void;
  onForget: (id: string) => void;
}

const formatRelativeTime = (timestamp: number) => {
  const diffMs = Date.now() - timestamp * 1000;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

export const MemoryGraphView: React.FC<MemoryGraphViewProps> = ({ memories, onPinToggle, onForget }) => {
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [hoverNode, setHoverNode] = useState<any>(null);
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [isLightMode, setIsLightMode] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

  useEffect(() => {
    const checkTheme = () => {
      const theme = document.documentElement.getAttribute('data-theme');
      setIsLightMode(theme === 'daylight');
    };
    checkTheme();
    
    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const resizeObserver = new ResizeObserver(entries => {
      if (entries[0]) {
        setDimensions({ width: entries[0].contentRect.width, height: entries[0].contentRect.height });
      }
    });
    resizeObserver.observe(containerRef.current);
    
    if (fgRef.current) {
      fgRef.current.d3Force('charge').strength(-300);
    }
    
    return () => resizeObserver.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const nodes: any[] = [];
    const links: any[] = [];
    const categories = new Set<string>();

    const stopWords = new Set(['the', 'and', 'user', 'that', 'with', 'this', 'from', 'have', 'what', 'which', 'about']);
    const extractKeywords = (text: string) => {
      const words = text.toLowerCase().replace(/[^a-z0-9\s]/g, '').split(/\s+/);
      return words.filter(w => w.length > 3 && !stopWords.has(w));
    };

    memories.forEach(m => {
      const cat = m.category || 'uncategorized';
      categories.add(cat);
      nodes.push({
        id: m.id,
        name: m.content,
        val: 1,
        isCategory: false,
        memory: m,
        category: cat,
        keywords: extractKeywords(m.content)
      });
    });

    categories.forEach(cat => {
      nodes.push({
        id: `cat-${cat}`,
        name: cat.toUpperCase(),
        val: 5,
        isCategory: true,
        category: cat
      });
    });

    // 1. Link memories to their categories
    memories.forEach(m => {
      const cat = m.category || 'uncategorized';
      links.push({
        source: m.id,
        target: `cat-${cat}`,
      });
    });

    // 2. Interconnect memories that share semantic keywords
    for (let i = 0; i < memories.length; i++) {
      const k1 = extractKeywords(memories[i].content);
      for (let j = i + 1; j < memories.length; j++) {
        const k2 = extractKeywords(memories[j].content);
        const intersection = k1.filter(k => k2.includes(k));
        if (intersection.length > 0) {
          links.push({
            source: memories[i].id,
            target: memories[j].id,
          });
        }
      }
    }

    return { nodes, links };
  }, [memories]);

  const handleNodeClick = useCallback((node: any) => {
    if (!node.isCategory) {
      setSelectedNode(node);
      
      // Center on node
      if (fgRef.current) {
        fgRef.current.centerAt(node.x, node.y, 1000);
        fgRef.current.zoom(2, 2000);
      }
    }
  }, []);

  if (memories.length === 0) {
    return (
      <EmptyState 
        title="No Memories Yet" 
        description="Arova will automatically extract facts and preferences as you converse."
      />
    );
  }

  return (
    <div style={isFullscreen ? { 
      position: 'fixed', 
      top: 0, 
      left: 0, 
      width: '100vw', 
      height: '100vh', 
      zIndex: 99999, 
      background: isLightMode ? '#f6f3eb' : '#14120e', 
      display: 'flex', 
      padding: '16px', 
      boxSizing: 'border-box' 
    } : { 
      display: 'flex', 
      width: '100%', 
      height: '100%', 
      position: 'relative' 
    }}>
      
      {/* Graph Area */}
      <div ref={containerRef} style={{ flex: 1, height: '100%', position: 'relative', overflow: 'hidden', borderRadius: '12px' }}>
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeLabel=""
          nodeColor={() => 'rgba(0,0,0,0)'}
          nodeRelSize={4}
          linkColor={() => isLightMode ? 'rgba(60, 50, 40, 0.25)' : 'rgba(255,255,255,0.18)'}
          linkWidth={isLightMode ? 0.8 : 0.5}
          onNodeClick={handleNodeClick}
          onNodeHover={setHoverNode}
          onEngineStop={() => {
            fgRef.current?.zoomToFit(500, 60);
          }}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const label = node.name;
            const isHovered = hoverNode?.id === node.id;
            const isSelected = selectedNode?.id === node.id;
            
            // Fixed screen sizes divided by globalScale so they look constant relative to screen
            const fontSize = node.isCategory ? 12/globalScale : 10/globalScale;
            const nodeRadius = node.isCategory ? 6/globalScale : 3/globalScale;
            
            // Draw glowing node
            ctx.beginPath();
            ctx.arc(node.x, node.y, nodeRadius, 0, 2 * Math.PI, false);
            
            ctx.shadowBlur = (isHovered || isSelected ? 16 : 8) / globalScale;
            
            if (isLightMode) {
              ctx.shadowColor = 'rgba(0, 0, 0, 0.25)';
              ctx.fillStyle = node.isCategory 
                ? (isHovered || isSelected ? '#000000' : '#1c1a17')
                : (isHovered || isSelected ? '#1c1a17' : '#4a433b');
            } else {
              ctx.shadowColor = 'rgba(255, 255, 255, 0.8)';
              ctx.fillStyle = isHovered || isSelected ? 'rgba(255, 255, 255, 1)' : 'rgba(255, 255, 255, 0.8)';
            }
            
            ctx.fill();
            
            // Reset shadow so text isn't blurry
            ctx.shadowBlur = 0;

            // Draw text directly below without a box
            if (globalScale >= 1.2 || node.isCategory || isHovered) {
              ctx.font = `${node.isCategory ? '700' : '500'} ${fontSize}px "Inter", "SF Pro Display", -apple-system, sans-serif`;
              ctx.textAlign = 'center';
              ctx.textBaseline = 'top';
              
              if (isLightMode) {
                ctx.fillStyle = node.isCategory 
                  ? '#11100f' 
                  : (isHovered || isSelected ? '#000000' : '#3d3730');
              } else {
                ctx.fillStyle = node.isCategory ? 'rgba(255, 255, 255, 0.95)' : 'rgba(255, 255, 255, 0.7)';
                if (isHovered || isSelected) {
                   ctx.fillStyle = 'rgba(255, 255, 255, 1)';
                }
              }
              
              const textY = node.y + nodeRadius + (6/globalScale);
              ctx.fillText(label.length > 45 ? label.substring(0, 45) + '...' : label, node.x, textY);
            }
          }}
        />
        
        {/* Floating Tooltip/Hint */}
        <div style={{ 
          position: 'absolute', 
          top: 16, 
          left: 16, 
          pointerEvents: 'none', 
          background: 'var(--glass-2)', 
          backdropFilter: 'blur(8px)',
          padding: '6px 14px', 
          borderRadius: '6px', 
          border: '1px solid var(--hairline-2)', 
          fontSize: '12px', 
          fontWeight: 500,
          color: 'var(--ink-2)' 
        }}>
          Scroll to zoom. Drag to pan. Click nodes to inspect.
        </div>

        {/* Floating Controls Toolbar */}
        <div style={{
          position: 'absolute',
          top: 16,
          right: selectedNode && selectedNode.memory ? 416 : 16,
          display: 'flex',
          gap: '8px',
          zIndex: 10,
          transition: 'right 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
        }}>
          {/* Recenter & Fit Button */}
          <button
            onClick={() => fgRef.current?.zoomToFit(400, 60)}
            title="Recenter & Fit Graph to Screen"
            style={{
              background: 'var(--glass-2)',
              backdropFilter: 'blur(8px)',
              border: '1px solid var(--hairline-2)',
              borderRadius: '8px',
              width: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: 'var(--ink)',
              transition: 'transform 0.15s ease, background-color 0.15s ease',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
            }}
            onMouseOver={e => {
              e.currentTarget.style.transform = 'scale(1.05)';
              e.currentTarget.style.backgroundColor = 'var(--glass-3)';
            }}
            onMouseOut={e => {
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.backgroundColor = 'var(--glass-2)';
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </button>

          {/* Full Screen Square Corners Toggle Button */}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            title={isFullscreen ? "Exit Full Screen (Esc)" : "View Full Screen Graph"}
            style={{
              background: 'var(--glass-2)',
              backdropFilter: 'blur(8px)',
              border: '1px solid var(--hairline-2)',
              borderRadius: '8px',
              width: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: 'var(--ink)',
              transition: 'transform 0.15s ease, background-color 0.15s ease',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
            }}
            onMouseOver={e => {
              e.currentTarget.style.transform = 'scale(1.05)';
              e.currentTarget.style.backgroundColor = 'var(--glass-3)';
            }}
            onMouseOut={e => {
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.backgroundColor = 'var(--glass-2)';
            }}
          >
            {isFullscreen ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 3v3a2 2 0 0 1-2 2H3" />
                <path d="M21 8h-3a2 2 0 0 1-2-2V3" />
                <path d="M3 16h3a2 2 0 0 1 2 2v3" />
                <path d="M16 21v-3a2 2 0 0 1 2-2h3" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 3H5a2 2 0 0 0-2 2v3" />
                <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
                <path d="M3 16v3a2 2 0 0 0 2 2h3" />
                <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Detail Overlay Panel */}
      {selectedNode && selectedNode.memory && (
        <div style={{
          width: '380px', 
          position: 'absolute',
          top: '24px',
          right: '24px',
          background: 'var(--glass-1)', 
          border: '1px solid var(--hairline-2)', 
          borderRadius: '12px', 
          padding: '24px', 
          display: 'flex', 
          flexDirection: 'column',
          zIndex: 20,
          boxShadow: '0 10px 40px rgba(0,0,0,0.5)'
        }}>
          <button 
            style={{ position: 'absolute', top: '16px', right: '16px', background: 'transparent', border: 'none', color: 'var(--ink-3)', cursor: 'pointer', padding: '4px' }}
            onClick={() => setSelectedNode(null)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
          
          <div style={{ fontSize: '16px', fontWeight: 500, color: 'var(--ink)', lineHeight: 1.5, marginBottom: '24px', marginTop: '12px', paddingRight: '12px' }}>
            {selectedNode.memory.content}
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '24px' }}>
            <div style={{ fontSize: '12px', color: 'var(--ink-2)', marginBottom: '8px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Metadata
            </div>
            {selectedNode.memory.why_remembered && <InfoRow label="Why" value={selectedNode.memory.why_remembered} />}
            <InfoRow label="Category" value={selectedNode.memory.category} />
            <InfoRow label="Continuity" value={`${Math.round((selectedNode.memory.continuity_value || 0.5) * 100)}%`} />
            <InfoRow label="Referenced" value={`${selectedNode.memory.reinforcement_count} times`} />
            <InfoRow label="Last Used" value={formatRelativeTime(selectedNode.memory.last_reinforced_at)} />
          </div>

          <div style={{ display: 'flex', gap: '12px', marginTop: 'auto' }}>
            <ActionButton 
              label={selectedNode.memory.decay_score === -1 ? 'Unpin' : 'Pin'} 
              variant={selectedNode.memory.decay_score === -1 ? 'primary' : 'secondary'}
              onClick={() => {
                onPinToggle(selectedNode.memory.id, selectedNode.memory.decay_score === -1);
                // Optimistic UI update in the panel
                setSelectedNode({
                  ...selectedNode,
                  memory: { ...selectedNode.memory, decay_score: selectedNode.memory.decay_score === -1 ? 0 : -1 }
                });
              }} 
            />
            <ActionButton 
              label="Forget" 
              variant="danger" 
              onClick={() => {
                onForget(selectedNode.memory.id);
                setSelectedNode(null);
              }} 
            />
          </div>
        </div>
      )}

    </div>
  );
};
