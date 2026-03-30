import { Component, type ReactNode, type ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

/**
 * A lightweight error boundary for individual page sections.
 * Unlike the top-level ErrorBoundary which replaces the entire page,
 * this renders a compact inline error card so other sections keep working.
 */

interface SectionErrorBoundaryProps {
  section?: string;
  fallbackTitle?: string;
  fallbackMessage?: string;
  children: ReactNode;
}

interface SectionErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class SectionErrorBoundary extends Component<SectionErrorBoundaryProps, SectionErrorBoundaryState> {
  constructor(props: SectionErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): SectionErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error(`[${this.props.section || 'Section'}] Error:`, error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Card className="border-destructive/50">
          <CardContent className="py-6">
            <div className="flex items-center gap-3 text-destructive">
              <AlertTriangle className="h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-medium">
                  {this.props.fallbackTitle || 'Something went wrong in this section'}
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  {this.props.fallbackMessage ||
                    'This section encountered an error. Other sections are still working.'}
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" className="mt-3" onClick={this.handleRetry}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
          </CardContent>
        </Card>
      );
    }
    return this.props.children;
  }
}

export default SectionErrorBoundary;
