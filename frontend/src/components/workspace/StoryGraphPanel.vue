<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { drag, type D3DragEvent } from 'd3-drag'
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type Simulation, type SimulationNodeDatum } from 'd3-force'
import { select, type Selection } from 'd3-selection'
import { zoom, zoomIdentity, type D3ZoomEvent, type ZoomBehavior } from 'd3-zoom'
import { CircleDot, GitBranch, MapPin, Maximize2, Users } from '@lucide/vue'

import type { StoryElementsSnapshot } from '@/api/projects'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

type GraphNodeType = 'character' | 'location' | 'event' | 'scene'

interface GraphNodeDetail extends SimulationNodeDatum {
  id: string
  type: GraphNodeType
  label: string
  caption: string
  detail: string
  radius: number
  color: string
}

interface GraphLink {
  id: string
  source: string | GraphNodeDetail
  target: string | GraphNodeDetail
  type: 'character-event' | 'event-location' | 'scene-character' | 'scene-location' | 'scene-event'
}

interface GraphRuntimeNode extends GraphNodeDetail {
  x: number
  y: number
}

type GraphRuntimeLink = Omit<GraphLink, 'source' | 'target'> & {
  source: string | GraphRuntimeNode
  target: string | GraphRuntimeNode
}

const props = defineProps<{
  storyElements?: StoryElementsSnapshot
}>()

const graphContainer = ref<HTMLElement>()
const fullscreenGraphContainer = ref<HTMLElement>()
const isGraphFullscreenOpen = ref(false)
const selectedNodeId = ref('')
let simulation: Simulation<GraphRuntimeNode, GraphRuntimeLink> | undefined
let zoomBehavior: ZoomBehavior<SVGSVGElement, unknown> | undefined

const graphNodes = computed<GraphNodeDetail[]>(() => {
  const elements = props.storyElements
  if (!elements) return []

  const characters = elements.characters.map((character) => ({
    id: character.id,
    type: 'character' as const,
    label: character.name,
    caption: shortLabel(character.name, 8),
    detail: character.description || character.motivation,
    radius: 6,
    color: '#2563eb',
  }))

  const events = elements.events.map((event, index) => ({
    id: event.id,
    type: 'event' as const,
    label: `事件 ${index + 1}`,
    caption: '事件',
    detail: event.summary,
    radius: 4.5,
    color: '#52525b',
  }))

  const locations = elements.locations.map((location) => ({
    id: location.id,
    type: 'location' as const,
    label: location.name,
    caption: shortLabel(location.name, 8),
    detail: location.description,
    radius: 5.5,
    color: '#059669',
  }))

  const scenes = elements.scenes.map((scene) => ({
    id: scene.id,
    type: 'scene' as const,
    label: scene.title,
    caption: shortLabel(scene.title, 8),
    detail: scene.summary || scene.dramatic_purpose,
    radius: 5,
    color: '#7c3aed',
  }))

  return [...characters, ...events, ...locations, ...scenes]
})

const graphLinks = computed<GraphLink[]>(() => {
  const elements = props.storyElements
  if (!elements) return []

  const characterIds = new Set(elements.characters.map((character) => character.id))
  const locationIds = new Set(elements.locations.map((location) => location.id))
  const eventIds = new Set(elements.events.map((event) => event.id))
  const links: GraphLink[] = []

  for (const event of elements.events) {
    for (const characterId of event.involved_characters) {
      if (characterIds.has(characterId)) {
        links.push({
          id: `${characterId}-${event.id}`,
          source: characterId,
          target: event.id,
          type: 'character-event',
        })
      }
    }

    for (const location of elements.locations) {
      if (event.summary.includes(location.name)) {
        links.push({
          id: `${event.id}-${location.id}`,
          source: event.id,
          target: location.id,
          type: 'event-location',
        })
      }
    }
  }

  for (const scene of elements.scenes) {
    for (const characterId of scene.characters) {
      if (characterIds.has(characterId)) {
        links.push({
          id: `${scene.id}-${characterId}`,
          source: scene.id,
          target: characterId,
          type: 'scene-character',
        })
      }
    }

    if (locationIds.has(scene.location_id)) {
      links.push({
        id: `${scene.id}-${scene.location_id}`,
        source: scene.id,
        target: scene.location_id,
        type: 'scene-location',
      })
    }

    for (const eventId of scene.source_events) {
      if (eventIds.has(eventId)) {
        links.push({
          id: `${scene.id}-${eventId}`,
          source: scene.id,
          target: eventId,
          type: 'scene-event',
        })
      }
    }
  }

  return links
})

const selectedNode = computed(() => {
  return graphNodes.value.find((node) => node.id === selectedNodeId.value)
})

const hasGraph = computed(() => graphNodes.value.length > 0)

const graphSignature = computed(() => {
  const elements = props.storyElements
  if (!elements) return ''

  const characters = elements.characters
    .map((character) => ({
      id: character.id,
      name: character.name,
      aliases: [...character.aliases].sort(),
      role: character.role,
      description: character.description,
      motivation: character.motivation,
    }))
    .sort((left, right) => left.id.localeCompare(right.id))
  const locations = elements.locations
    .map((location) => ({
      id: location.id,
      name: location.name,
      description: location.description,
    }))
    .sort((left, right) => left.id.localeCompare(right.id))
  const events = elements.events
    .map((event) => ({
      id: event.id,
      source_chapter: event.source_chapter,
      summary: event.summary,
      involved_characters: [...event.involved_characters].sort(),
    }))
    .sort((left, right) => left.id.localeCompare(right.id))
  const scenes = elements.scenes
    .map((scene) => ({
      id: scene.id,
      title: scene.title,
      source_chapter: scene.source_chapter,
      location_id: scene.location_id,
      characters: [...scene.characters].sort(),
      source_events: [...scene.source_events].sort(),
      summary: scene.summary,
      dramatic_purpose: scene.dramatic_purpose,
      key_beats: [...scene.key_beats],
      time_of_day: scene.time_of_day,
    }))
    .sort((left, right) => left.id.localeCompare(right.id))

  return JSON.stringify({ characters, locations, events, scenes })
})

onMounted(() => {
  renderGraph({ resetView: true })
})

onBeforeUnmount(() => {
  simulation?.stop()
  simulation = undefined
})

watch(graphSignature, () => renderGraph({ resetView: true }))
watch(isGraphFullscreenOpen, () => renderGraph({ resetView: true }))

async function renderGraph(options: { resetView?: boolean } = {}) {
  await nextTick()
  const container = currentGraphContainer()
  if (!container || graphNodes.value.length === 0) {
    simulation?.stop()
    simulation = undefined
    if (container) {
      select(container).selectAll('*').remove()
    }
    return
  }

  const previousPositions = captureNodePositions()
  simulation?.stop()
  select(container).selectAll('*').remove()

  const width = Math.max(480, container.clientWidth)
  const height = Math.max(420, container.clientHeight)
  const nodes: GraphRuntimeNode[] = graphNodes.value.map((node, index) => {
    const previousPosition = previousPositions.get(node.id)
    return {
      ...node,
      x: previousPosition?.x ?? width / 2 + Math.cos(index) * 80,
      y: previousPosition?.y ?? height / 2 + Math.sin(index) * 80,
    }
  })
  const links: GraphRuntimeLink[] = graphLinks.value.map((link) => ({
    id: link.id,
    source: linkSourceId(link.source),
    target: linkSourceId(link.target),
    type: link.type,
  }))

  const svg = select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('class', 'h-full w-full cursor-grab bg-white active:cursor-grabbing')

  const viewport = svg.append('g')
  const linkLayer = viewport.append('g').attr('stroke-linecap', 'round')
  const nodeLayer = viewport.append('g')

  const linkSelection = linkLayer
    .selectAll<SVGLineElement, GraphRuntimeLink>('line')
    .data(links, (link) => link.id)
    .join('line')
    .attr('stroke', (link) => linkColor(link.type))
    .attr('stroke-width', 1.15)
    .attr('stroke-opacity', 0.68)

  const nodeSelection = nodeLayer
    .selectAll<SVGGElement, GraphRuntimeNode>('g')
    .data(nodes, (node) => node.id)
    .join((enter) => {
      const group = enter.append('g').attr('class', 'cursor-pointer')
      group
        .append('circle')
        .attr('r', (node) => node.radius)
        .attr('fill', (node) => node.color)
        .attr('stroke', '#ffffff')
        .attr('stroke-width', 2)
      group
        .append('text')
        .attr('x', 0)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .attr('fill', '#3f3f46')
        .attr('font-size', 11)
        .attr('font-weight', 500)
        .text((node) => node.caption)
      return group
    })
    .on('click', (event, node) => {
      event.stopPropagation()
      selectedNodeId.value = node.id
      updateSelectedNode(nodeSelection)
    })

  const dragBehavior = drag<SVGGElement, GraphRuntimeNode>()
    .on('start', (event, node) => handleDragStart(event, node))
    .on('drag', (event, node) => handleDrag(event, node))
    .on('end', (event, node) => handleDragEnd(event, node))
  nodeSelection.call(dragBehavior)

  zoomBehavior = zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.25, 3])
    .wheelDelta((event) => -event.deltaY * (event.deltaMode === 1 ? 0.05 : 0.0016))
    .on('zoom', (event: D3ZoomEvent<Element, unknown>) => {
      viewport.attr('transform', event.transform.toString())
    })
  svg.call(zoomBehavior)
  svg.on('click', () => {
    selectedNodeId.value = ''
    updateSelectedNode(nodeSelection)
  })

  simulation = forceSimulation<GraphRuntimeNode>(nodes)
    .force('link', forceLink<GraphRuntimeNode, GraphRuntimeLink>(links).id((node) => node.id).distance(120).strength(0.34))
    .force('charge', forceManyBody<GraphRuntimeNode>().strength(-420).distanceMin(34).distanceMax(620))
    .force('collide', forceCollide<GraphRuntimeNode>().radius((node) => node.radius + 34).strength(0.92))
    .force('x', forceX<GraphRuntimeNode>(width / 2).strength(0.025))
    .force('y', forceY<GraphRuntimeNode>(height / 2).strength(0.025))
    .force('center', forceCenter(width / 2, height / 2))
    .alpha(0.9)
    .alphaDecay(0.018)
    .velocityDecay(0.36)
    .on('tick', () => {
      linkSelection
        .attr('x1', (link) => nodeX(link.source))
        .attr('y1', (link) => nodeY(link.source))
        .attr('x2', (link) => nodeX(link.target))
        .attr('y2', (link) => nodeY(link.target))
      nodeSelection.attr('transform', (node) => `translate(${node.x},${node.y})`)
    })

  if (selectedNodeId.value && !nodes.some((node) => node.id === selectedNodeId.value)) {
    selectedNodeId.value = ''
  }
  updateSelectedNode(nodeSelection)
  if (options.resetView ?? false) {
    fitGraph()
  }
}

function currentGraphContainer(): HTMLElement | undefined {
  return isGraphFullscreenOpen.value ? fullscreenGraphContainer.value : graphContainer.value
}

function openFullscreenGraph() {
  if (!hasGraph.value) return
  isGraphFullscreenOpen.value = true
}

function fitGraph() {
  const container = currentGraphContainer()
  if (!container || !zoomBehavior) return

  const svg = select(container).select<SVGSVGElement>('svg')
  if (!svg.node()) return

  svg.call(zoomBehavior.transform, zoomIdentity)
}

function captureNodePositions(): Map<string, { x: number, y: number }> {
  const positions = new Map<string, { x: number, y: number }>()
  for (const node of simulation?.nodes() ?? []) {
    if (Number.isFinite(node.x) && Number.isFinite(node.y)) {
      positions.set(node.id, { x: node.x, y: node.y })
    }
  }
  return positions
}

function handleDragStart(event: D3DragEvent<SVGGElement, GraphRuntimeNode, GraphRuntimeNode>, node: GraphRuntimeNode) {
  if (!event.active) simulation?.alphaTarget(0.18).restart()
  node.fx = node.x
  node.fy = node.y
}

function handleDrag(event: D3DragEvent<SVGGElement, GraphRuntimeNode, GraphRuntimeNode>, node: GraphRuntimeNode) {
  node.fx = event.x
  node.fy = event.y
}

function handleDragEnd(event: D3DragEvent<SVGGElement, GraphRuntimeNode, GraphRuntimeNode>, node: GraphRuntimeNode) {
  if (!event.active) simulation?.alphaTarget(0)
  node.fx = null
  node.fy = null
}

function updateSelectedNode(selection: Selection<SVGGElement, GraphRuntimeNode, SVGGElement, unknown>) {
  selection
    .select('circle')
    .attr('stroke', (node) => node.id === selectedNodeId.value ? '#111827' : '#ffffff')
    .attr('stroke-width', (node) => node.id === selectedNodeId.value ? 3 : 2)
}

function nodeX(node: string | GraphRuntimeNode): number {
  return typeof node === 'string' ? 0 : node.x
}

function nodeY(node: string | GraphRuntimeNode): number {
  return typeof node === 'string' ? 0 : node.y
}

function linkSourceId(node: string | GraphNodeDetail): string {
  return typeof node === 'string' ? node : node.id
}

function typeLabel(type: GraphNodeType): string {
  const labels: Record<GraphNodeType, string> = {
    character: '角色',
    event: '事件',
    location: '地点',
    scene: '场景',
  }
  return labels[type]
}

function linkColor(type: GraphLink['type']): string {
  const colors: Record<GraphLink['type'], string> = {
    'character-event': '#bfdbfe',
    'event-location': '#bbf7d0',
    'scene-character': '#ddd6fe',
    'scene-location': '#a7f3d0',
    'scene-event': '#fde68a',
  }
  return colors[type]
}

function shortLabel(value: string, maxLength: number): string {
  const text = value.trim()
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text
}
</script>

<template>
  <Card class="flex min-h-0 flex-col overflow-hidden">
    <CardHeader class="shrink-0">
      <div class="flex items-start justify-between gap-3">
        <div>
          <CardTitle class="flex items-center gap-2 text-base">
            <GitBranch class="size-4" />
            故事图谱
          </CardTitle>
          <CardDescription>角色、地点和事件的关系视图。</CardDescription>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <Badge v-if="storyElements" variant="secondary">
            {{ storyElements.characters.length + storyElements.locations.length + storyElements.events.length + storyElements.scenes.length }} 节点
          </Badge>
          <Button v-if="hasGraph" size="sm" variant="outline" @click="openFullscreenGraph">
            <Maximize2 class="size-4" />
          </Button>
        </div>
      </div>
    </CardHeader>

    <CardContent class="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <div
        v-if="hasGraph"
        class="relative min-h-[430px] flex-1 overflow-hidden rounded-lg border bg-white"
      >
        <div ref="graphContainer" class="absolute inset-0" />
        <div
          v-if="selectedNode"
          class="absolute right-3 top-3 z-10 w-[min(260px,calc(100%-1.5rem))] rounded-lg border bg-background/95 p-3 shadow-sm backdrop-blur"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="truncate text-sm font-medium">{{ selectedNode.label }}</p>
              <p class="mt-0.5 text-xs text-muted-foreground">{{ typeLabel(selectedNode.type) }}</p>
            </div>
            <Badge class="shrink-0" variant="outline">{{ selectedNode.id }}</Badge>
          </div>
          <p class="mt-2 line-clamp-4 text-xs leading-5 text-muted-foreground">
            {{ selectedNode.detail || '暂无说明。' }}
          </p>
        </div>
      </div>

      <div
        v-else
        class="flex min-h-[430px] flex-1 flex-col items-center justify-center rounded-lg border border-dashed bg-muted/20 text-center"
      >
        <CircleDot class="size-8 text-muted-foreground" />
        <p class="mt-3 text-sm font-medium">暂无故事图谱</p>
        <p class="mt-1 text-xs text-muted-foreground">完成故事元素抽取后会显示角色、地点和事件关系。</p>
      </div>

      <div v-if="storyElements" class="grid grid-cols-4 gap-2">
        <div class="rounded-lg border bg-background p-3">
          <div class="flex items-center gap-2 text-xs text-blue-600">
            <Users class="size-3.5" />
            角色
          </div>
          <p class="mt-1 text-xl font-semibold text-blue-600">{{ storyElements.characters.length }}</p>
        </div>
        <div class="rounded-lg border bg-background p-3">
          <div class="flex items-center gap-2 text-xs text-emerald-600">
            <MapPin class="size-3.5" />
            地点
          </div>
          <p class="mt-1 text-xl font-semibold text-emerald-600">{{ storyElements.locations.length }}</p>
        </div>
        <div class="rounded-lg border bg-background p-3">
          <div class="flex items-center gap-2 text-xs text-zinc-600">
            <GitBranch class="size-3.5" />
            事件
          </div>
          <p class="mt-1 text-xl font-semibold text-zinc-600">{{ storyElements.events.length }}</p>
        </div>
        <div class="rounded-lg border bg-background p-3">
          <div class="flex items-center gap-2 text-xs text-violet-600">
            <CircleDot class="size-3.5" />
            场景
          </div>
          <p class="mt-1 text-xl font-semibold text-violet-600">{{ storyElements.scenes.length }}</p>
        </div>
      </div>

    </CardContent>
  </Card>

  <Dialog v-model:open="isGraphFullscreenOpen">
    <DialogContent
      class="flex h-[calc(100vh-2rem)] !w-[calc(100vw-2rem)] !max-w-none flex-col overflow-hidden p-0"
    >
      <DialogHeader class="shrink-0 border-b px-5 py-4">
        <div class="flex items-start justify-between gap-3 pr-10">
          <div>
            <DialogTitle class="flex items-center gap-2 text-base">
              <GitBranch class="size-4" />
              故事图谱
            </DialogTitle>
            <p class="mt-1 text-sm text-muted-foreground">点击节点查看角色、地点或事件摘要。</p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <Badge v-if="storyElements" variant="secondary">
              {{ storyElements.characters.length + storyElements.locations.length + storyElements.events.length + storyElements.scenes.length }} 节点
            </Badge>
            <Button size="sm" variant="outline" @click="fitGraph">
              <Maximize2 class="size-4" />
            </Button>
          </div>
        </div>
      </DialogHeader>

      <div class="relative min-h-0 flex-1 bg-muted/30 p-4">
        <div ref="fullscreenGraphContainer" class="h-full min-h-0 overflow-hidden rounded-lg border bg-white" />
        <div
          v-if="selectedNode"
          class="absolute right-8 top-8 z-10 w-[min(320px,calc(100%-4rem))] rounded-lg border bg-background/95 p-4 shadow-sm backdrop-blur"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="truncate text-sm font-medium">{{ selectedNode.label }}</p>
              <p class="mt-0.5 text-xs text-muted-foreground">{{ typeLabel(selectedNode.type) }}</p>
            </div>
            <Badge class="shrink-0" variant="outline">{{ selectedNode.id }}</Badge>
          </div>
          <p class="mt-3 text-xs leading-5 text-muted-foreground">
            {{ selectedNode.detail || '暂无说明。' }}
          </p>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
