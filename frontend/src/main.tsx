import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './design-system/index.css';
import 'katex/dist/katex.min.css';
import { invoke } from '@tauri-apps/api/core';

if (typeof window !== 'undefined') {
  window.addEventListener('error', (e) => {
    invoke('log_from_frontend', { msg: 'GLOBAL ERROR: ' + e.message + ' at ' + e.filename + ':' + e.lineno }).catch(()=>{});
  });
  window.addEventListener('unhandledrejection', (e) => {
    invoke('log_from_frontend', { msg: 'UNHANDLED REJECTION: ' + String(e.reason) }).catch(()=>{});
  });
  invoke('log_from_frontend', { msg: 'MAIN.TSX STARTING & ERROR HANDLERS ATTACHED' }).catch(()=>{});
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
