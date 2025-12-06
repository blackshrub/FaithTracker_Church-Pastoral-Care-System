/**
 * Member Detail Loading Skeleton
 * Shows animated placeholder UI while member data loads
 */

import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

export function MemberDetailSkeleton() {
  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Back button skeleton */}
      <Skeleton className="h-9 w-24" />

      {/* Profile Header skeleton */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row gap-6">
            {/* Avatar */}
            <Skeleton className="h-32 w-32 rounded-full mx-auto md:mx-0" />

            {/* Info */}
            <div className="flex-1 space-y-4 text-center md:text-left">
              <div className="space-y-2">
                <Skeleton className="h-8 w-48 mx-auto md:mx-0" />
                <Skeleton className="h-6 w-24 mx-auto md:mx-0" />
              </div>

              <div className="flex flex-wrap gap-4 justify-center md:justify-start">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-5 w-28" />
                <Skeleton className="h-5 w-36" />
              </div>

              {/* Action buttons */}
              <div className="flex gap-2 justify-center md:justify-start">
                <Skeleton className="h-10 w-28" />
                <Skeleton className="h-10 w-28" />
                <Skeleton className="h-10 w-10" />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs skeleton */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-10 w-28 flex-shrink-0" />
        ))}
      </div>

      {/* Timeline/Content skeleton */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-9 w-36" />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <TimelineEventSkeleton key={i} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function TimelineEventSkeleton() {
  return (
    <div className="flex gap-4 p-4 border rounded-lg">
      <div className="flex flex-col items-center">
        <Skeleton className="h-10 w-10 rounded-full" />
        <Skeleton className="h-full w-0.5 mt-2" />
      </div>
      <div className="flex-1 space-y-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <div className="flex gap-2 mt-2">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 w-24" />
        </div>
      </div>
    </div>
  );
}

export default MemberDetailSkeleton;
