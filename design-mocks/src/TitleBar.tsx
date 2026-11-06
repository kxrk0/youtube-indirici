import { Minus, Square, X } from 'lucide-react'

/** Windows 11 başlık çubuğu; FluentWindow'daki gibi uygulama içine çizilir. */
export function TitleBar({ className, title = 'YouTube Studio Downloader' }: { className: string; title?: string }) {
  return (
    <div className={className}>
      <span>{title}</span>
      <div aria-hidden="true" style={{ display: 'flex', height: '100%' }}>
        {[Minus, Square, X].map((Icon, i) => (
          <span key={i} style={{ width: 46, display: 'grid', placeItems: 'center' }}>
            <Icon size={i === 1 ? 11 : 14} strokeWidth={1.5} />
          </span>
        ))}
      </div>
    </div>
  )
}
