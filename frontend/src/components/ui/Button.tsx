import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: 'primary' | 'secondary' | 'quiet' | 'danger';
  readonly size?: 'small' | 'medium' | 'large';
  readonly children: ReactNode;
}

export function Button({ variant = 'primary', size = 'medium', className = '', children, ...props }: ButtonProps) {
  return <button className={`button button--${variant} button--${size}${className ? ` ${className}` : ''}`} {...props}>{children}</button>;
}
