import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { ExternalLink, FolderOpen, Plus, RotateCcw, Trash2 } from 'lucide-react'
import { api, onBridgeEvent, type Rule, type Schedule, type Settings as SettingsValues, type Subscription } from '../bridge'
import { useStore } from '../store'
import { SPRING_SEGMENT, Switch } from '../components/Controls'

const AUDIO_QUALITIES: [SettingsValues['audio_quality'], string][] = [['0', 'En iyi'], ['320', '320k'], ['256', '256k'], ['192', '192k'], ['128', '128k']]
const SPEED_PRESETS = [0, 1, 5, 10, 25]
/** Kaydırıcı bırakılmadan her adımda yazmasın. */
const SLIDER_SAVE_DELAY_MS = 350
const DEVELOPERS = [['Proje sahibi', 'https://github.com/kxrk0'], ['Geliştirici', 'https://github.com/swaffX']] as const

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="am-set-section">
      <h2>{title}</h2>
      <div className="am-set-rows">{children}</div>
    </section>
  )
}

function Row({ label, hint, children, wide }: { label: string; hint?: ReactNode; children: ReactNode; wide?: boolean }) {
  return (
    <div className="am-set-row" data-wide={wide}>
      <div className="am-set-label">
        <strong>{label}</strong>
        {hint && <span>{hint}</span>}
      </div>
      <div className="am-set-control">{children}</div>
    </div>
  )
}

function Slider({ value, min, max, onCommit, label }: { value: number; min: number; max: number; onCommit: (v: number) => void; label: string }) {
  const [local, setLocal] = useState(value)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => setLocal(value), [value])
  const pct = ((local - min) / (max - min)) * 100
  return (
    <input type="range" className="am-range" min={min} max={max} step={1} value={local} aria-label={label}
      style={{ '--pct': `${pct}%` } as React.CSSProperties}
      onChange={(e) => {
        const v = Number(e.target.value)
        setLocal(v)
        window.clearTimeout(timer.current)
        timer.current = window.setTimeout(() => onCommit(v), SLIDER_SAVE_DELAY_MS)
      }} />
  )
}

function TextSetting({ value, placeholder, onCommit, multiline, label }: { value: string; placeholder?: string; onCommit: (v: string) => void; multiline?: boolean; label: string }) {
  const [local, setLocal] = useState(value)
  useEffect(() => setLocal(value), [value])
  const commit = () => { if (local !== value) onCommit(local) }
  return multiline ? (
    <textarea className="am-set-input" rows={3} value={local} placeholder={placeholder} aria-label={label}
      onChange={(e) => setLocal(e.target.value)} onBlur={commit} />
  ) : (
    <input className="am-set-input" value={local} placeholder={placeholder} aria-label={label}
      onChange={(e) => setLocal(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }} />
  )
}

function Segmented<T extends string>({ options, value, onChange, id }: { options: [T, string][]; value: T; onChange: (v: T) => void; id: string }) {
  return (
    <div className="am-seg" role="radiogroup" style={{ marginBottom: 0 }}>
      {options.map(([v, label]) => (
        <button key={v} role="radio" aria-checked={value === v} onClick={() => onChange(v)}>
          {value === v && <motion.span layoutId={`am-set-${id}`} className="am-seg-ind" transition={SPRING_SEGMENT} />}
          <span className="am-seg-text">{label}</span>
        </button>
      ))}
    </div>
  )
}

export function Settings() {
  const store = useStore()
  const [values, setValues] = useState<SettingsValues | null>(null)
  const [meta, setMeta] = useState<{ appVersion: string; ytdlpVersion: string; frozen: boolean } | null>(null)
  const [latest, setLatest] = useState<string | null | undefined>(undefined)
  const [updating, setUpdating] = useState(false)
  const [proxyResult, setProxyResult] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    api().settings().then((r) => { setValues(r.values); setMeta(r) }).catch((err) => store.notify(`Ayarlar okunamadı: ${err?.message ?? err}`, 'error'))
    api().ytdlp_latest().then(setLatest).catch(() => setLatest(null))
  }, [store])

  const save = useCallback(<K extends keyof SettingsValues>(key: K, value: SettingsValues[K]) => {
    const previous = values?.[key]
    setValues((v) => v && { ...v, [key]: value })
    api().set_setting(key, value).catch((err) => {
      setValues((v) => v && previous !== undefined ? { ...v, [key]: previous } : v)
      store.notify(`Kaydedilemedi: ${err?.message ?? err}`, 'error')
    })
  }, [values, store])

  if (!values || !meta) return <div className="am-page-pad"><h1 className="am-page-title">Ayarlar</h1></div>

  const stale = latest && meta.ytdlpVersion && latest !== meta.ytdlpVersion

  return (
    <div className="am-page-pad">
      <h1 className="am-page-title">Ayarlar</h1>

      <Section title="İndirme">
        <Row label="İndirme klasörü" hint={values.download_dir}>
          <button className="am-ghost" onClick={() => api().pick_folder(values.download_dir).then((d) => d && save('download_dir', d))}>
            <FolderOpen size={15} strokeWidth={1.8} /> Klasör seç
          </button>
        </Row>
        <Row label="Hız sınırı" hint={values.speed_limit ? `${values.speed_limit} MB/s` : 'Sınırsız'}>
          <div className="am-set-stack">
            <Slider value={values.speed_limit} min={0} max={50} label="Hız sınırı (MB/s)" onCommit={(v) => save('speed_limit', v)} />
            <div className="am-set-presets">
              {SPEED_PRESETS.map((p) => (
                <button key={p} className="am-text-btn" aria-pressed={values.speed_limit === p} onClick={() => save('speed_limit', p)}>{p ? `${p} MB/s` : 'Sınırsız'}</button>
              ))}
            </div>
          </div>
        </Row>
        <Row label="Aynı anda indirme" hint={`${values.max_concurrent} indirme birlikte; fazlası sırada bekler.`}>
          <Slider value={values.max_concurrent} min={1} max={8} label="Aynı anda indirme" onCommit={(v) => save('max_concurrent', v)} />
        </Row>
        <Row label="Parçalı indirme" hint={`${values.fragment_downloads} parça birlikte. Yavaş bağlantıda 2, hızlıda 16.`}>
          <Slider value={values.fragment_downloads} min={1} max={16} label="Parçalı indirme" onCommit={(v) => save('fragment_downloads', v)} />
        </Row>
        <Row label="MP3 kalitesi" hint="Yalnız ses indirmelerinde bit hızı.">
          <Segmented id="aq" options={AUDIO_QUALITIES} value={values.audio_quality} onChange={(v) => save('audio_quality', v)} />
        </Row>
        <Row label="Platforma göre klasörle" hint="YouTube, SoundCloud gibi her platform ayrı alt klasöre.">
          <Switch on={values.auto_organize} onToggle={() => save('auto_organize', !values.auto_organize)} label="" ariaLabel="Platforma göre klasörle" />
        </Row>
        <Row label="Dosya adı şablonu" hint="yt-dlp şablonu, ör. %(uploader)s - %(title)s.%(ext)s">
          <TextSetting label="Dosya adı şablonu" value={values.filename_template} placeholder="%(title)s.%(ext)s" onCommit={(v) => save('filename_template', v)} />
        </Row>
        <Row label="Bitince bilgisayarı kapat" hint="Tüm indirmeler bitince 30 saniye sonra kapanır.">
          <Switch on={values.auto_shutdown} onToggle={() => save('auto_shutdown', !values.auto_shutdown)} label="" ariaLabel="Bitince bilgisayarı kapat" />
        </Row>
      </Section>

      <Section title="Ağ">
        <Row label="Proxy" hint={proxyResult ? <span className={proxyResult.ok ? undefined : 'am-error-text'}>{proxyResult.text}</span> : 'Ör. http://kullanıcı:şifre@sunucu:port'}>
          <div className="am-set-inline">
            <TextSetting label="Proxy" value={values.proxy} placeholder="http://sunucu:port" onCommit={(v) => { setProxyResult(null); save('proxy', v) }} />
            <button className="am-ghost" disabled={!values.proxy} onClick={() => {
              setProxyResult({ ok: true, text: 'Deneniyor…' })
              api().test_proxy(values.proxy).then((t) => setProxyResult({ ok: true, text: t }))
                .catch((err) => setProxyResult({ ok: false, text: `Bağlanamadı: ${err?.message ?? err}` }))
            }}>Dene</button>
          </div>
        </Row>
        <Row label="Yedek proxy listesi" hint="Her satıra bir proxy. İndirme hata verince sıradakine geçilir." wide>
          <TextSetting label="Yedek proxy listesi" multiline value={values.proxy_pool} placeholder={'http://sunucu1:port\nhttp://sunucu2:port'} onCommit={(v) => save('proxy_pool', v)} />
        </Row>
        <Row label="FFmpeg ek argümanları" hint="Uzman ayarı; ör. -vf scale=1280:720">
          <TextSetting label="FFmpeg ek argümanları" value={values.custom_ffmpeg_args} onCommit={(v) => save('custom_ffmpeg_args', v)} />
        </Row>
      </Section>

      <Section title="Otomasyon">
        <Schedules />
        <Subscriptions hours={values.sub_check_hours} onHours={(h) => save('sub_check_hours', h)} />
        <Rules />
      </Section>

      <Section title="Kütüphane">
        <Row label="Ek klasörler" hint="Kütüphane indirme klasörüne ek olarak bunları da tarar. Her satıra bir klasör." wide>
          <TextSetting label="Ek kütüphane klasörleri" multiline value={values.library_folders} placeholder={'C:\\Users\\Ben\\Müzik\nD:\\Videolar'} onCommit={(v) => save('library_folders', v)} />
        </Row>
      </Section>

      <Section title="Entegrasyon">
        <Row label="Webhook" hint="Her indirme bitince bu adrese JSON gönderilir (Zapier, n8n…).">
          <TextSetting label="Webhook adresi" value={values.webhook_url} placeholder="https://…" onCommit={(v) => save('webhook_url', v)} />
        </Row>
        <Row label="Eklentiler" hint="plugins klasöründeki Python eklentileri.">
          <div className="am-set-inline">
            <button className="am-ghost" onClick={() => api().open_plugins_folder()}>Klasörü aç</button>
            <button className="am-ghost" onClick={() => api().reload_plugins().then((n) => store.notify(`${n} eklenti yüklendi.`))
              .catch((err) => store.notify(`Eklentiler yüklenemedi: ${err?.message ?? err}`, 'error'))}>Yeniden yükle</button>
          </div>
        </Row>
      </Section>

      <Section title="Sürüm">
        <Row label="İndirme motoru (yt-dlp)" hint={
          meta.frozen ? `Kurulu ${meta.ytdlpVersion}. EXE sürümünde motor uygulamayla birlikte güncellenir.`
            : latest === undefined ? `Kurulu ${meta.ytdlpVersion}. Güncel sürüm kontrol ediliyor…`
            : stale ? `Kurulu ${meta.ytdlpVersion}, güncel ${latest}. İndirme hataları için güncellemen önerilir.`
            : `Kurulu ${meta.ytdlpVersion}${latest ? ', güncel' : ''}.`}>
          <button className="am-ghost" disabled={meta.frozen || updating} onClick={() => {
            setUpdating(true)
            api().update_ytdlp().then((m) => store.notify(m)).catch((err) => store.notify(`Güncellenemedi: ${err?.message ?? err}`, 'error'))
              .finally(() => setUpdating(false))
          }}>{updating ? 'Güncelleniyor' : 'Güncelle'}</button>
        </Row>
        <Row label="Uygulama" hint={`Sürüm ${meta.appVersion}`}>
          <div className="am-set-inline">
            {DEVELOPERS.map(([label, url]) => (
              <button key={url} className="am-text-btn" style={{ color: 'var(--text-2)' }} onClick={() => api().open_url(url)}>
                {label} <ExternalLink size={13} strokeWidth={1.8} />
              </button>
            ))}
          </div>
        </Row>
      </Section>
    </div>
  )
}

function Schedules() {
  const store = useStore()
  const [items, setItems] = useState<Schedule[]>([])
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [time, setTime] = useState('')
  const [daily, setDaily] = useState(false)
  const [type, setType] = useState<'video' | 'audio'>('video')
  const load = useCallback(() => { api().schedules().then(setItems).catch((err) => store.notify(`Görevler okunamadı: ${err?.message ?? err}`, 'error')) }, [store])
  useEffect(load, [load])
  const add = () => {
    // Günlük görev "SS:DD", tek seferlik "YYYY-AA-GG SS:DD" (datetime-local 'T' ile gelir).
    const when = daily ? time.slice(-5) : time.replace('T', ' ')
    api().add_schedule({ url, name, when, daily, type }).then(() => { setUrl(''); setName(''); load(); store.notify('Görev eklendi.') })
      .catch((err) => store.notify(`Eklenemedi: ${err?.message ?? err}`, 'error'))
  }
  return (
    <Row label="Zamanlanmış indirmeler" hint="Belirli bir anda ya da her gün aynı saatte başlar. Uygulama açık olmalı; kapalıyken geçen tek seferlik görev açılışta başlar." wide>
      <div className="am-set-stack">
        {items.length > 0 && (
          <ul className="am-set-list">
            {items.map((t) => (
              <li key={t.id}>
                <div><strong>{t.name}</strong><span>{t.daily ? `Her gün ${t.when}` : t.when}, {t.type === 'audio' ? 'ses' : 'video'}</span></div>
                <button className="am-icon-btn" aria-label="Görevi sil" onClick={() => api().delete_schedule(t.id).then(load)}><Trash2 size={15} strokeWidth={1.8} /></button>
              </li>
            ))}
          </ul>
        )}
        <div className="am-set-form">
          <input className="am-set-input" placeholder="Bağlantı" value={url} onChange={(e) => setUrl(e.target.value)} aria-label="Bağlantı" />
          <input className="am-set-input" placeholder="Ad (isteğe bağlı)" value={name} onChange={(e) => setName(e.target.value)} aria-label="Görev adı" />
          <input className="am-set-input" type={daily ? 'time' : 'datetime-local'} value={time} onChange={(e) => setTime(e.target.value)} aria-label="Zaman" />
          <Switch on={daily} onToggle={() => { setDaily((d) => !d); setTime('') }} label="Her gün" />
          <Segmented id="sch-type" options={[['video', 'Video'], ['audio', 'Ses']]} value={type} onChange={setType} />
          <button className="am-primary" disabled={!url || !time} onClick={add}><Plus size={15} strokeWidth={2.2} /> Ekle</button>
        </div>
      </div>
    </Row>
  )
}

function Subscriptions({ hours, onHours }: { hours: number; onHours: (h: number) => void }) {
  const store = useStore()
  const [items, setItems] = useState<Subscription[]>([])
  const [url, setUrl] = useState('')
  const [type, setType] = useState<'video' | 'audio'>('video')
  const load = useCallback(() => { api().subscriptions().then(setItems).catch((err) => store.notify(`Abonelikler okunamadı: ${err?.message ?? err}`, 'error')) }, [store])
  useEffect(load, [load])
  useEffect(() => onBridgeEvent((e) => { if (e.type === 'subscriptions-changed') load() }), [load])
  return (
    <Row label="Kanal abonelikleri" hint={`Her ${hours} saatte bir yeni videolar kendiliğinden indirilir. Daha önce indirilenler atlanır.`} wide>
      <div className="am-set-stack">
        <Slider value={hours} min={1} max={24} label="Kontrol sıklığı (saat)" onCommit={onHours} />
        {items.length > 0 && (
          <ul className="am-set-list">
            {items.map((s) => (
              <li key={s.id}>
                <div><strong>{s.name}</strong><span>{s.type === 'audio' ? 'Ses' : 'Video'}{s.lastChecked ? `, son kontrol ${s.lastChecked.slice(0, 16)}` : ', henüz kontrol edilmedi'}</span></div>
                <button className="am-icon-btn" aria-label="Aboneliği sil" onClick={() => api().delete_subscription(s.id).then(load)}><Trash2 size={15} strokeWidth={1.8} /></button>
              </li>
            ))}
          </ul>
        )}
        <div className="am-set-form">
          <input className="am-set-input" placeholder="Kanal ya da oynatma listesi bağlantısı" value={url} onChange={(e) => setUrl(e.target.value)} aria-label="Abonelik bağlantısı" />
          <Segmented id="sub-type" options={[['video', 'Video'], ['audio', 'Ses']]} value={type} onChange={setType} />
          <button className="am-primary" disabled={!url} onClick={() => api().add_subscription(url, type).then(() => { setUrl(''); load() })
            .catch((err) => store.notify(`Eklenemedi: ${err?.message ?? err}`, 'error'))}><Plus size={15} strokeWidth={2.2} /> Abone ol</button>
        </div>
      </div>
    </Row>
  )
}

const FIELD_LABEL: Record<Rule['match_field'], string> = { title: 'Başlık', url: 'Bağlantı', channel: 'Kanal' }

function Rules() {
  const store = useStore()
  const [items, setItems] = useState<Rule[]>([])
  const [draft, setDraft] = useState<Rule>({ name: '', match_field: 'title', pattern: '', output_subdir: '', type_override: '' })
  const load = useCallback(() => { api().rules().then(setItems).catch((err) => store.notify(`Kurallar okunamadı: ${err?.message ?? err}`, 'error')) }, [store])
  useEffect(load, [load])
  return (
    <Row label="Otomatik klasör kuralları" hint="Başlık, bağlantı ya da kanal desene uyarsa indirme o alt klasöre gider. Desen düzenli ifadedir, büyük-küçük harf fark etmez." wide>
      <div className="am-set-stack">
        <ul className="am-set-list">
          {items.map((r) => (
            <li key={r.name}>
              <div><strong>{r.name}</strong><span>{FIELD_LABEL[r.match_field]} ~ {r.pattern} → {r.output_subdir || '(aynı klasör)'}</span></div>
              <button className="am-icon-btn" aria-label="Kuralı sil" onClick={() => api().delete_rule(r.name).then(load)}><Trash2 size={15} strokeWidth={1.8} /></button>
            </li>
          ))}
        </ul>
        <div className="am-set-form">
          <input className="am-set-input" placeholder="Kural adı" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} aria-label="Kural adı" />
          <Segmented id="rule-field" options={[['title', 'Başlık'], ['url', 'Bağlantı'], ['channel', 'Kanal']]} value={draft.match_field}
            onChange={(v) => setDraft({ ...draft, match_field: v })} />
          <input className="am-set-input" placeholder="Desen, ör. podcast|bölüm" value={draft.pattern} onChange={(e) => setDraft({ ...draft, pattern: e.target.value })} aria-label="Desen" />
          <input className="am-set-input" placeholder="Alt klasör" value={draft.output_subdir} onChange={(e) => setDraft({ ...draft, output_subdir: e.target.value })} aria-label="Alt klasör" />
          <button className="am-primary" disabled={!draft.name || !draft.pattern} onClick={() => api().add_rule(draft)
            .then(() => { setDraft({ ...draft, name: '', pattern: '', output_subdir: '' }); load() })
            .catch((err) => store.notify(`Eklenemedi: ${err?.message ?? err}`, 'error'))}><Plus size={15} strokeWidth={2.2} /> Ekle</button>
          <button className="am-text-btn" style={{ color: 'var(--text-2)' }} onClick={() => api().reset_rules().then(load)}><RotateCcw size={13} strokeWidth={1.8} /> Varsayılanlara dön</button>
        </div>
      </div>
    </Row>
  )
}
