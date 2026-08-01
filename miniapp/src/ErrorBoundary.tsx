import React from 'react';

interface State {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="app-state">
          <div className="app-state-icon">⚠️</div>
          <div className="app-state-title">Что-то сломалось</div>
          <div className="app-state-text">{this.state.error.message}</div>
        </div>
      );
    }
    return this.props.children;
  }
}
