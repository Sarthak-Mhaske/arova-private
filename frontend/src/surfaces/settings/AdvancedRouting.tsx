import React, { useState, useEffect } from 'react';
import { socket } from '../../runtime/socket';

export const AdvancedRouting: React.FC = () => {
  const [customRouting, setCustomRouting] = useState({
    chat: 'auto',
    reasoning: 'auto',
    embeddings: 'auto',
    summarization: 'auto',
    vision: 'auto'
  });
  
  const [activeRoutes] = useState<Record<string, string>>({});
  
  useEffect(() => {
    // We could listen to config.sync to hydrate the custom routing
    // and listen to provider.fallback for activeRoutes.
  }, []);

  const handleOverrideChange = (capability: string, provider: string) => {
    const newRouting = { ...customRouting, [capability]: provider };
    setCustomRouting(newRouting);
    
    // Auto-save via WebSocket
    socket.sendEvent({
      type: 'config.update_request',
      config: {
        custom_routing: newRouting
      }
    });
  };

  const capabilities = [
    { id: 'chat', label: 'Chat' },
    { id: 'reasoning', label: 'Reasoning' },
    { id: 'embeddings', label: 'Embeddings' },
    { id: 'summarization', label: 'Summarization' },
    { id: 'vision', label: 'Vision' },
  ];

  return (
    <div style={{ marginTop: '2rem', background: '#1a1a1a', padding: '2rem', borderRadius: '8px' }}>
      <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>Advanced Routing</h2>
      <p style={{ color: '#aaa', marginBottom: '2rem' }}>
        Override specific cognitive capabilities with custom providers.
      </p>
      
      <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #333' }}>
            <th style={{ paddingBottom: '1rem' }}>Capability</th>
            <th style={{ paddingBottom: '1rem' }}>Provider Override</th>
            <th style={{ paddingBottom: '1rem' }}>Active Route</th>
          </tr>
        </thead>
        <tbody>
          {capabilities.map(cap => (
            <tr key={cap.id} style={{ borderBottom: '1px solid #222' }}>
              <td style={{ padding: '1rem 0', fontWeight: 'bold' }}>{cap.label}</td>
              <td style={{ padding: '1rem 0' }}>
                <select 
                  value={(customRouting as any)[cap.id]}
                  onChange={(e) => handleOverrideChange(cap.id, e.target.value)}
                  style={{ padding: '8px', background: '#333', color: '#fff', border: 'none', borderRadius: '4px', width: '150px' }}
                >
                  <option value="auto">Auto</option>
                  <option value="groq">Groq</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama</option>
                </select>
              </td>
              <td style={{ padding: '1rem 0', color: '#888' }}>
                {activeRoutes[cap.id] ? (
                  <span style={{ color: '#a55' }}>{activeRoutes[cap.id]} (Fallback)</span>
                ) : (
                  <span style={{ color: '#5a5' }}>{(customRouting as any)[cap.id] === 'auto' ? 'Managed by Policy' : (customRouting as any)[cap.id]}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
