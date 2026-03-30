/**
 * PageLoader - Loading fallback for lazy-loaded routes
 * Provides a consistent loading experience during code-splitting
 */

import { Loader2 } from 'lucide-react';

export default function PageLoader() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background">
      <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
      <p className="text-sm text-muted-foreground">Loading...</p>
    </div>
  );
}
