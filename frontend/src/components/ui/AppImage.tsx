import { useEffect, useRef, useState } from 'react'
import type { ProductImage } from '@/types'
import { catalogService } from '@/services/catalogService'

interface AppImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  /** Product id used to request a fresh signed URL after expiry. */
  productId?: number
  /** Image id used to locate the refreshed signed URL. */
  imageId?: number
}

// Several thumbnails for the same product expire together. Share one refresh
// request per product instead of issuing one request per broken <img>.
const refreshInFlight = new Map<number, Promise<ProductImage[]>>()
function refreshImages(productId: number): Promise<ProductImage[]> {
  const existing = refreshInFlight.get(productId)
  if (existing) return existing
  const pending = catalogService.listImages(productId).finally(() => {
    if (refreshInFlight.get(productId) === pending) refreshInFlight.delete(productId)
  })
  refreshInFlight.set(productId, pending)
  return pending
}

/** Image that silently refreshes its short-lived signed URL on load failure. */
export function AppImage({ src, productId, imageId, onError, ...props }: AppImageProps) {
  const [url, setUrl] = useState(src)
  const retried = useRef(false)

  useEffect(() => {
    setUrl(src)
    retried.current = false
    return () => {
      retried.current = true
    }
  }, [src, productId, imageId])

  return (
    <img
      {...props}
      src={url}
      loading="lazy"
      decoding="async"
      onError={(event) => {
        onError?.(event)
        if (retried.current || !productId || !imageId) return
        retried.current = true
        const requestedSrc = url
        void refreshImages(productId)
          .then((images) => {
            if (requestedSrc !== url) return
            const fresh = images.find((image) => image.id === imageId)
            if (fresh?.image_url) setUrl(fresh.image_url)
          })
          .catch(() => {
            // Keep the original src; a later data refetch can still recover it.
          })
      }}
    />
  )
}
