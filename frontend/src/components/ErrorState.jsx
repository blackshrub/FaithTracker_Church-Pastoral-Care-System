/**
 * ErrorState - Displays when an error occurs
 * Provides friendly error messaging with retry option
 */

import { Button } from '@/components/ui/button';
import { AlertCircle, RefreshCw, WifiOff, ServerCrash } from 'lucide-react';

const errorTypes = {
  network: {
    icon: WifiOff,
    title: 'Connection problem',
    description: 'Please check your internet connection and try again.'
  },
  server: {
    icon: ServerCrash,
    title: 'Server error',
    description: 'Something went wrong on our end. Please try again in a moment.'
  },
  default: {
    icon: AlertCircle,
    title: 'Something went wrong',
    description: 'An unexpected error occurred. Please try again.'
  }
};

function getErrorType(error) {
  if (!error) return 'default';

  const message = error.message?.toLowerCase() || '';
  const status = error.response?.status;

  if (message.includes('network') || message.includes('fetch') || !navigator.onLine) {
    return 'network';
  }

  if (status >= 500) {
    return 'server';
  }

  return 'default';
}

export function ErrorState({
  error,
  onRetry,
  title,
  description,
  className = ''
}) {
  const errorType = getErrorType(error);
  const config = errorTypes[errorType];
  const IconComponent = config.icon;

  return (
    <div className={`flex flex-col items-center justify-center py-12 px-4 text-center animate-fade-in ${className}`}>
      <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
        <IconComponent className="w-8 h-8 text-destructive" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">
        {title || config.title}
      </h3>
      <p className="text-sm text-muted-foreground max-w-sm mb-6">
        {description || config.description}
      </p>
      {onRetry && (
        <Button onClick={onRetry} variant="outline" className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Try Again
        </Button>
      )}
    </div>
  );
}

// For use in React Query error handling
export function QueryErrorState({ error, refetch }) {
  return (
    <ErrorState
      error={error}
      onRetry={refetch}
    />
  );
}

export default ErrorState;
