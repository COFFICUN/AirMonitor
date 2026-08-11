interface AiriMascotProps {
  readonly className?: string;
  readonly label?: string;
  readonly compact?: boolean;
  readonly priority?: boolean;
}

export function AiriMascot({
  className = '',
  label,
  compact = false,
  priority = false,
}: AiriMascotProps) {
  return (
    <img
      className={`airi-mascot${compact ? ' airi-mascot--compact' : ''}${className ? ` ${className}` : ''}`}
      src="/airi-field-robot.webp"
      alt={label ?? ''}
      width="1024"
      height="1536"
      loading={priority ? 'eager' : 'lazy'}
      fetchPriority={priority ? 'high' : 'auto'}
      decoding="async"
    />
  );
}
