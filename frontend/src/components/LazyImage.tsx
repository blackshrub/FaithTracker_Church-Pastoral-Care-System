import { useState, useMemo } from 'react';

interface PhotoUrls {
  thumbnail?: string;
  medium?: string;
  large?: string;
}

/**
 * LazyImage component with srcset support for responsive images
 *
 * Supports two modes:
 * 1. Single src: Just pass `src` prop
 * 2. Responsive srcset: Pass `photoUrls` object with thumbnail, medium, large keys
 *    This reduces bandwidth by 40-60% on mobile devices
 *
 * Backend generates 3 sizes: thumbnail (100x100), medium (300x300), large (600x600)
 */

interface LazyImageProps {
  src?: string;
  photoUrls?: PhotoUrls;
  alt: string;
  className?: string;
  placeholderClassName?: string;
  sizes?: string;
  onLoad?: () => void;
  onError?: () => void;
}

export const LazyImage = ({
  src,
  photoUrls,
  alt,
  className = '',
  placeholderClassName = 'bg-gray-200 animate-pulse',
  sizes = '(max-width: 640px) 100px, (max-width: 1024px) 300px, 600px',
  onLoad,
  onError
}: LazyImageProps) => {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  // Build srcset from photoUrls if available
  const { imageSrc, srcSet } = useMemo(() => {
    if (photoUrls && typeof photoUrls === 'object') {
      const srcSetParts: string[] = [];
      if (photoUrls.thumbnail) srcSetParts.push(`${photoUrls.thumbnail} 100w`);
      if (photoUrls.medium) srcSetParts.push(`${photoUrls.medium} 300w`);
      if (photoUrls.large) srcSetParts.push(`${photoUrls.large} 600w`);

      return {
        imageSrc: photoUrls.medium || photoUrls.large || photoUrls.thumbnail || src,
        srcSet: srcSetParts.length > 0 ? srcSetParts.join(', ') : undefined
      };
    }
    return { imageSrc: src, srcSet: undefined };
  }, [src, photoUrls]);

  const handleLoad = () => {
    setIsLoading(false);
    onLoad && onLoad();
  };

  const handleError = () => {
    setIsLoading(false);
    setHasError(true);
    onError && onError();
  };

  return (
    <div className={`relative ${className}`}>
      {isLoading && !hasError && (
        <div className={`w-full h-full ${placeholderClassName}`} />
      )}
      {hasError ? (
        <div className="w-full h-full bg-gray-100 flex items-center justify-center text-gray-400 text-xs">
          ❌
        </div>
      ) : (
        <img
          src={imageSrc}
          srcSet={srcSet}
          sizes={srcSet ? sizes : undefined}
          alt={alt}
          loading="lazy"
          decoding="async"
          className={`w-full h-full object-cover transition-opacity duration-200 ${isLoading ? 'opacity-0' : 'opacity-100'}`}
          onLoad={handleLoad}
          onError={handleError}
        />
      )}
    </div>
  );
};

export default LazyImage;
