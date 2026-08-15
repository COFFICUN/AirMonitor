import { Component, type ErrorInfo, type ReactNode } from 'react';

interface AppErrorBoundaryProps {
  readonly children: ReactNode;
  readonly label: string;
}

interface AppErrorBoundaryState {
  readonly failed: boolean;
}

export class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  override state: AppErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { failed: true };
  }

  override componentDidCatch(_error: Error, _info: ErrorInfo): void {
    // The UI intentionally does not expose raw render errors. Production
    // instrumentation can be added at this boundary without changing callers.
  }

  override render() {
    if (this.state.failed) {
      return (
        <section className="panel visualization-fallback" role="alert">
          <h2>{this.props.label}</h2>
          <p>Этот блок временно недоступен. Остальная панель продолжает работать.</p>
        </section>
      );
    }
    return this.props.children;
  }
}
