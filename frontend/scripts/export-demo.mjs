// Exports the backend's sample reviews to src/demo/snapshot.json for the hosted, backend-free demo.
// Usage: start the API (port 8000), then `node scripts/export-demo.mjs`.
import { mkdirSync, writeFileSync } from 'node:fs'

const API = process.env.API_URL ?? 'http://127.0.0.1:8000/api'
const get = async (path) => {
  const response = await fetch(API + path)
  if (!response.ok) throw new Error(`${path}: ${response.status}`)
  return response
}

// Reload the sample set so the snapshot is pristine, whatever was triaged before.
const seeded = await fetch(`${API}/demo/sample-data`, { method: 'POST' })
if (!seeded.ok) throw new Error(`Could not load sample data: ${seeded.status}`)

const summaries = await (await get('/reviews?limit=200')).json()
const reviews = []
const events = {}
for (const summary of summaries.filter((review) => review.is_sample)) {
  reviews.push(await (await get(`/reviews/${summary.id}`)).json())
  const text = await (await get(`/reviews/${summary.id}/stream`)).text()
  events[summary.id] = text
    .split('\n\n')
    .filter((block) => block.startsWith('id:'))
    .map((block) => {
      const lines = Object.fromEntries(block.split('\n').map((line) => [line.slice(0, line.indexOf(': ')), line.slice(line.indexOf(': ') + 2)]))
      return { id: Number(lines.id), type: lines.event, data: JSON.parse(lines.data) }
    })
}

const repos = (await (await get('/repos')).json()).filter((repo) => repo.owner === 'reviewmind-demo')

mkdirSync(new URL('../src/demo/', import.meta.url), { recursive: true })
writeFileSync(
  new URL('../src/demo/snapshot.json', import.meta.url),
  JSON.stringify({ exported_at: new Date().toISOString(), reviews, events, repos }),
)
console.log(`Exported ${reviews.length} reviews, ${repos.length} repositories`)
