import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Spinner } from '@fluentui/react-components'
import type { ServiceMapData, ServiceMapNode } from '../api/types'
import { ErrorNotice } from '../components/ErrorNotice'
import { IncidentPriorityBadge } from '../components/IncidentPriorityBadge'
import { useApiResource } from '../hooks/use-api-resource'
import styles from './ServiceMapPage.module.css'

const NODE_WIDTH = 168
const NODE_HEIGHT = 46
const COLUMN_GAP = 90
const ROW_GAP = 22

/** Layered layout: services nothing else relies on sit on the left, foundations on the right. */
function layout(data: ServiceMapData) {
  const depth = new Map<number, number>()
  data.nodes.forEach((node) => depth.set(node.id, 0))
  for (let pass = 0; pass < data.nodes.length; pass += 1) {
    data.edges.forEach((edge) => depth.set(edge.dependsOn, Math.max(depth.get(edge.dependsOn) ?? 0, (depth.get(edge.service) ?? 0) + 1)))
  }
  const columns = new Map<number, ServiceMapNode[]>()
  data.nodes.forEach((node) => columns.set(depth.get(node.id)!, [...(columns.get(depth.get(node.id)!) ?? []), node]))
  const positions = new Map<number, { x: number; y: number }>()
  columns.forEach((nodes, column) => nodes.forEach((node, row) =>
    positions.set(node.id, { x: 16 + column * (NODE_WIDTH + COLUMN_GAP), y: 16 + row * (NODE_HEIGHT + ROW_GAP) })))
  const width = 32 + columns.size * (NODE_WIDTH + COLUMN_GAP) - COLUMN_GAP
  const height = 32 + Math.max(...[...columns.values()].map((nodes) => nodes.length), 1) * (NODE_HEIGHT + ROW_GAP) - ROW_GAP
  return { positions, width, height }
}

export function ServiceMapPage() {
  const { data, error, isLoading, reload } = useApiResource<ServiceMapData>('/service-map/', undefined, 30000)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const shape = useMemo(() => (data ? layout(data) : null), [data])
  if (isLoading && !data) return <div className={styles['service-map-page']}><Spinner label="Loading the map" /></div>
  if (error && !data) return <div className={styles['service-map-page']}><ErrorNotice message={error.message} onRetry={reload} /></div>
  if (!data || !shape) return null

  const byId = new Map(data.nodes.map((node) => [node.id, node]))
  const selected = selectedId ? byId.get(selectedId) : undefined
  const related = new Set(selected ? [...selected.reliesOn, ...selected.affects, selected.id] : [])
  const names = (ids: number[]) => ids.map((id) => byId.get(id)?.name).filter(Boolean).join(', ')

  return (
    <div className={styles['service-map-page']}>
      <header>
        <h1>Service map</h1>
        <p className={styles['service-map-page__lead']}>
          Arrows point to what a service relies on. Colour shows open incidents. Select a service to see what it affects.
        </p>
      </header>
      <div className={styles['service-map-page__layout']}>
        <div className={styles['service-map-page__canvas']}>
          <svg width={shape.width} height={shape.height} role="img" aria-label="Service dependency map">
            <defs>
              <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M0 0 L8 4 L0 8 z" fill="currentColor" />
              </marker>
            </defs>
            {data.edges.map((edge) => {
              const from = shape.positions.get(edge.service)!
              const to = shape.positions.get(edge.dependsOn)!
              const x1 = from.x + NODE_WIDTH, y1 = from.y + NODE_HEIGHT / 2, x2 = to.x, y2 = to.y + NODE_HEIGHT / 2
              const dim = selected && !(related.has(edge.service) && related.has(edge.dependsOn))
              return <path key={`${edge.service}-${edge.dependsOn}`} d={`M${x1} ${y1} C${x1 + 45} ${y1}, ${x2 - 45} ${y2}, ${x2 - 2} ${y2}`}
                fill="none" stroke="currentColor" strokeWidth="1.2" markerEnd="url(#arrow)" className={styles['service-map-page__edge']} opacity={dim ? 0.15 : 0.7} />
            })}
            {data.nodes.map((node) => {
              const position = shape.positions.get(node.id)!
              return (
                <g key={node.id} transform={`translate(${position.x} ${position.y})`} tabIndex={0} role="button"
                  aria-label={`${node.name}, ${node.health}`} onClick={() => setSelectedId(node.id === selectedId ? null : node.id)}
                  onKeyDown={(event) => { if (event.key === 'Enter') setSelectedId(node.id) }}
                  opacity={selected && !related.has(node.id) ? 0.35 : 1}
                  className={`${styles['service-map-page__node']} ${styles[`service-map-page__node--${node.health}`]}`}>
                  <rect width={NODE_WIDTH} height={NODE_HEIGHT} rx="4" className={styles['service-map-page__node-box']} />
                  <rect width="5" height={NODE_HEIGHT} className={styles['service-map-page__node-mark']} />
                  <text x="16" y="20" className={styles['service-map-page__node-name']}>{node.name}</text>
                  <text x="16" y="36" className={styles['service-map-page__node-meta']}>
                    {node.openIncidents ? `${node.openIncidents} open` : 'No open incidents'}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>
        <aside className={styles['service-map-page__detail']}>
          {selected ? (
            <>
              <h2>{selected.name}</h2>
              <p>{selected.openIncidents === 0 ? 'Healthy.' : `${selected.openIncidents} open incident${selected.openIncidents === 1 ? '' : 's'}.`} {selected.worstPriority && <IncidentPriorityBadge priority={selected.worstPriority} />}</p>
              <p><strong>Relies on:</strong> {names(selected.reliesOn) || 'nothing else'}</p>
              <p><strong>If it fails, affects:</strong> {names(selected.affects) || 'no other service'}</p>
              <p className={styles['service-map-page__lead']}>Business criticality {selected.businessCriticality} of 5.</p>
              <Link to={`/incidents?service=${selected.id}&scope=open`}>See its incidents</Link>
            </>
          ) : <p className={styles['service-map-page__lead']}>Nothing selected.</p>}
        </aside>
      </div>
    </div>
  )
}
