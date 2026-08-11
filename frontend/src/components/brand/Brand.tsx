import { Link } from 'react-router';

export function Brand({ to = '/' }: { readonly to?: string }) {
  return (
    <Link className="brand" to={to} aria-label="AirMonitor — на главную">
      <span className="brand__mark" aria-hidden="true"><span /><span /><span /></span>
      <span className="brand__copy"><strong>AirMonitor</strong><small>Воздух Алматы</small></span>
    </Link>
  );
}
