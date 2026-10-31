import { useEffect, useState } from 'react'
import { RotateCcw } from 'lucide-react'
import { api } from '../services/api'
import LanguageSelect from '../components/LanguageSelect'
import PageHeader, { Button } from '../components/PageHeader'

const Section = ({ title, children }) => (
  <section>
    <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-stone-500">{title}</h2>
    <div className="divide-y divide-stone-200 rounded-xl border border-stone-200 bg-white px-4">{children}</div>
  </section>
)
const Row = ({ label, hint, children }) => (
  <div className="flex items-center justify-between gap-6 py-3">
    <div>
      <div className="text-sm font-medium">{label}</div>
      {hint && <div className="text-xs text-stone-500">{hint}</div>}
    </div>
    <div className="shrink-0">{children}</div>
  </div>
)
const selectCls = 'rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-stone-500'

function Status({ label, ok, detail }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5 text-sm">
      <span className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${ok ? 'bg-teal-600' : 'bg-stone-300'}`} />{label}</span>
      <span className="truncate text-xs text-stone-500" title={detail}>{detail}</span>
    </div>
  )
}

export default function Settings({ settings, updateSettings, reset }) {
  const [models, setModels] = useState([])
  const [mics, setMics] = useState([])
  const [health, setHealth] = useState(null)
  const [system, setSystem] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get('/llm/models').then(setModels).catch(() => {})
    api.get('/voice/devices').then(setMics).catch((e) => setError(e.message))
  }, [])
  useEffect(() => {
    const tick = () => {
      api.get('/health').then(setHealth).catch(() => setHealth(null))
      api.get('/system').then(setSystem).catch(() => {})
    }
    tick()
    const id = setInterval(tick, 5000)
    return () => clearInterval(id)
  }, [])

  if (!settings) return <div className="p-8 text-sm text-stone-500">Loading settings… (is the backend running?)</div>
  const set = (k, v) => updateSettings({ [k]: v }).catch((e) => setError(e.message))
  const modelList = models.includes(settings.llm_model) ? models : [settings.llm_model, ...models]
  const piperVoices = health?.piper?.voices?.length ? health.piper.voices : [settings.piper_voice]

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Settings" subtitle="Changes apply immediately and are saved locally.">
        <Button variant="ghost" onClick={reset}><RotateCcw size={15} /> Reset to defaults</Button>
      </PageHeader>
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="mx-auto max-w-3xl space-y-8">
          {error && <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm text-rose-800">{error}</p>}

          <Section title="Language">
            <Row label="Language" hint="Auto detects English or Tamil from your voice and text.">
              <LanguageSelect value={settings.language} onChange={(v) => set('language', v)} />
            </Row>
          </Section>

          <Section title="Voice">
            <Row label="Microphone">
              <select className={selectCls} value={settings.mic_device ?? ''} onChange={(e) => set('mic_device', e.target.value === '' ? null : Number(e.target.value))}>
                <option value="">System default</option>
                {mics.map((m) => <option key={m.index} value={m.index}>{m.name} ({m.hostapi})</option>)}
              </select>
            </Row>
            <Row label="Speech recognition model" hint="Runs on CPU (INT8). Larger is more accurate but slower.">
              <select className={selectCls} value={settings.whisper_model} onChange={(e) => set('whisper_model', e.target.value)}>
                {['tiny', 'base', 'small', 'medium'].map((m) => <option key={m}>{m}</option>)}
              </select>
            </Row>
            <Row label="English voice (Piper)">
              <select className={selectCls} value={settings.piper_voice} onChange={(e) => set('piper_voice', e.target.value)}>
                {piperVoices.map((v) => <option key={v}>{v}</option>)}
              </select>
            </Row>
            <Row label={`Speech speed · ${Number(settings.voice_speed).toFixed(2)}×`}>
              <input type="range" min="0.6" max="1.6" step="0.05" value={settings.voice_speed}
                onChange={(e) => set('voice_speed', Number(e.target.value))} className="w-44 accent-stone-900" />
            </Row>
            <Row label="Speak replies aloud">
              <select className={selectCls} value={settings.speak_replies} onChange={(e) => set('speak_replies', e.target.value)}>
                <option value="voice">When I used voice</option>
                <option value="always">Always</option>
                <option value="never">Never</option>
              </select>
            </Row>
          </Section>

          <Section title="Language model">
            <Row label="Model" hint="Any model pulled in Ollama.">
              <select className={selectCls} value={settings.llm_model} onChange={(e) => set('llm_model', e.target.value)}>
                {modelList.map((m) => <option key={m}>{m}</option>)}
              </select>
            </Row>
            <Row label={`Temperature · ${Number(settings.temperature).toFixed(2)}`}>
              <input type="range" min="0" max="1.2" step="0.05" value={settings.temperature}
                onChange={(e) => set('temperature', Number(e.target.value))} className="w-44 accent-stone-900" />
            </Row>
            <Row label="Context window (tokens)" hint="Lower values use less memory.">
              <select className={selectCls} value={settings.num_ctx} onChange={(e) => set('num_ctx', Number(e.target.value))}>
                {[1024, 2048, 3072, 4096, 6144, 8192].map((n) => <option key={n}>{n}</option>)}
              </select>
            </Row>
            <Row label="Max reply length (tokens)">
              <select className={selectCls} value={settings.max_tokens} onChange={(e) => set('max_tokens', Number(e.target.value))}>
                {[150, 250, 400, 600, 1000].map((n) => <option key={n}>{n}</option>)}
              </select>
            </Row>
            <Row label="GPU layers" hint="Auto lets Ollama decide. 0 forces CPU. Changing it reloads the model.">
              <select className={selectCls} value={settings.num_gpu} onChange={(e) => set('num_gpu', Number(e.target.value))}>
                <option value={-1}>Auto</option>
                <option value={0}>0 (CPU only)</option>
                {[10, 15, 20, 25, 30].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </Row>
          </Section>

          <Section title="System status">
            <Status label="Ollama" ok={health?.llm?.ok} detail={health?.llm?.ok ? (health.llm.model_available ? `${health.llm.model} ready` : `${health.llm.model} not pulled`) : health?.llm?.error || 'Backend offline'} />
            <Status label="Speech recognition" ok={!!health?.whisper_loaded} detail={health?.whisper_loaded ? `${health.whisper_loaded} loaded` : 'loads on first use'} />
            <Status label="English voice (Piper)" ok={health?.piper?.ok} detail={health?.piper?.ok ? health.piper.voice : health?.piper?.error} />
            <Status label="Tamil voice (Indic-TTS)" ok={health?.tamil_tts?.ok} detail={health?.tamil_tts?.ok ? 'running' : 'optional · text-only fallback'} />
            <Status label="Documents indexed" ok={(health?.documents || 0) > 0} detail={String(health?.documents ?? 0)} />
            {system && (
              <>
                <Status label="RAM" ok detail={`${system.ram_used_mb} / ${system.ram_total_mb} MB used · backend ${system.backend_rss_mb} MB`} />
                <Status label="GPU memory" ok={!system.gpu_error} detail={system.gpu_error ? 'unavailable' : `${system.vram_used_mb} / ${system.vram_total_mb} MB used`} />
                {system.ollama_loaded?.map((m) => (
                  <Status key={m.name} label={`Loaded: ${m.name}`} ok detail={`${m.vram_mb} MB on GPU of ${m.size_mb} MB`} />
                ))}
              </>
            )}
          </Section>
        </div>
      </div>
    </div>
  )
}
