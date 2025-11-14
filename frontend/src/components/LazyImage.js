import React, { useState, useRef, useEffect } from 'react';

export const LazyImage = ({ 
  src, 
  alt, 
  className = '', 
  placeholderClassName = 'bg-gray-200 animate-pulse',
  onLoad,
  onError 
}) => {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [isIntersecting, setIsIntersecting] = useState(false);
  const imgRef = useRef();

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsIntersecting(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1, rootMargin: '50px' }
    );

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }

    return () => observer.disconnect();
  }, []);

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
    <div ref={imgRef} className={`relative ${className}`}>
      {!isIntersecting || isLoading ? (
        <div className={`w-full h-full ${placeholderClassName}`} />
      ) : null}
      {isIntersecting && (
        <>
          {hasError ? (
            <div className="w-full h-full bg-gray-100 flex items-center justify-center text-gray-400 text-xs">
              ❌
            </div>
          ) : (
            <img
              src={src}
              alt={alt}
              className={`w-full h-full object-cover transition-opacity duration-200 ${isLoading ? 'opacity-0' : 'opacity-100'}`}
              onLoad={handleLoad}
              onError={handleError}
            />
          )}
        </>
      )}
    </div>
  );
};

export default LazyImage;