import React from 'react';

interface ActionChipProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  primary?: boolean;
}

export const ActionChip: React.FC<ActionChipProps> = ({ primary, children, className = '', ...props }) => {
  return (
    <button className={`action-chip ${primary ? 'primary' : ''} ${className}`} {...props}>
      {children}
    </button>
  );
};
