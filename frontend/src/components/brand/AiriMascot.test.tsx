import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AiriMascot } from './AiriMascot';

describe('AiriMascot', () => {
  it('renders the generated field robot with stable dimensions', () => {
    render(<AiriMascot label="Айри приветствует участника" />);
    const mascot = screen.getByRole('img', { name: 'Айри приветствует участника' });
    expect(mascot).toHaveAttribute('src', '/airi-field-robot.webp');
    expect(mascot).toHaveAttribute('width', '1024');
    expect(mascot).toHaveAttribute('height', '1536');
  });

  it('can be decorative without adding an image landmark', () => {
    render(<AiriMascot />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });
});
