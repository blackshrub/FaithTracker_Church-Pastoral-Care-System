import { lazy, Suspense } from 'react';

import { Skeleton } from '@/components/ui/skeleton';

// Lazy load chart components - Chart.js only loads when charts are rendered
const LazyPieChart = lazy(() => import('./PieChart'));
const LazyBarChart = lazy(() => import('./BarChart'));
const LazyAreaChart = lazy(() => import('./AreaChart'));

// Chart loading fallback
const ChartSkeleton = ({ height = 300 }) => (
  <div style={{ height: `${height}px` }} className="flex items-center justify-center">
    <Skeleton className="w-full h-full rounded-lg" />
  </div>
);

// Wrapper components with Suspense
export const PieChart = (props) => (
  <Suspense fallback={<ChartSkeleton height={props.height} />}>
    <LazyPieChart {...props} />
  </Suspense>
);

export const BarChart = (props) => (
  <Suspense fallback={<ChartSkeleton height={props.height} />}>
    <LazyBarChart {...props} />
  </Suspense>
);

export const AreaChart = (props) => (
  <Suspense fallback={<ChartSkeleton height={props.height} />}>
    <LazyAreaChart {...props} />
  </Suspense>
);

// Also export default for single imports
export default { PieChart, BarChart, AreaChart };
