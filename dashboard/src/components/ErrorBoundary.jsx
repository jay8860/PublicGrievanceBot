// Contains a single page's failure instead of blanking the whole portal.
import React from 'react';
import { ErrorState } from './feedback';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
    this.reset = this.reset.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Keep the details in the console for developers, show a calm message to users.
    console.error('Page failed to render', error, info);
  }

  reset() {
    this.setState({ error: null });
  }

  render() {
    if (this.state.error) {
      return (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <ErrorState message={this.state.error.message} onRetry={this.reset} />
        </div>
      );
    }
    return this.props.children;
  }
}
