import './glass.css';
import './atmosphere.css';

export interface MaterialProps {
  variant?: 'glass' | 'glass-command' | 'glass-surface' | 'glass-anchor' | 'glass-awareness';
  className?: string;
}
