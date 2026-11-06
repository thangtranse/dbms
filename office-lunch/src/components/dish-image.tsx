import Image, { type ImageLoader } from "next/image";

// Resize Unsplash only; preserve source recipe image URLs for other providers.
const unsplashLoader: ImageLoader = ({ src, width, quality }) =>
  src.startsWith("https://images.unsplash.com/")
    ? `${src}?w=${width}&q=${quality ?? 70}&auto=format&fit=crop`
    : src;

export function DishImage({ src, alt, sizes, className = "", priority }: { src: string; alt: string; sizes: string; className?: string; priority?: boolean }) {
  return (
    <div className={`relative overflow-hidden bg-surface-2 ${className}`}>
      {src && <Image loader={unsplashLoader} src={src} alt={alt} fill sizes={sizes} priority={priority} className="object-cover" />}
    </div>
  );
}
