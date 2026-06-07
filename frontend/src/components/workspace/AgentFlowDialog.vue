<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Activity,
  CheckCircle2,
  Circle,
  Database,
  FileCheck2,
  FileCode2,
  GitBranch,
  Loader2,
  Sparkles,
  TriangleAlert,
} from '@lucide/vue'

import type { AIRun, StoryElementsSnapshot } from '@/api/projects'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatTime, taskLabel } from '@/lib/workspace-formatters'

type AgentNodeId =
  | 'chapters'
  | 'chapter_agent'
  | 'card_agent'
  | 'card_store'
  | 'scene_planner'
  | 'yaml_writer'
  | 'memory_agent'
  | 'validator'
  | 'repair_agent'
  | 'script_result'

type AgentNodeStatus = 'pending' | 'running' | 'succeeded' | 'failed'

interface AgentNode {
  id: AgentNodeId
  label: string
  caption: string
  x: number
  y: number
}

interface AgentLink {
  source: AgentNodeId
  target: AgentNodeId
}

interface StreamMessage {
  id: string
  type: string
  node: string
  title: string
  content: string
  meta: string
}

interface NodeDetail {
  purpose: string
  input: string
  output: string
  note: string
}

const props = defineProps<{
  aiRuns: AIRun[]
  chapterCount: number
  storyElements?: StoryElementsSnapshot
  scriptVersionName?: string
}>()

const open = defineModel<boolean>('open', { required: true })
const sideTab = ref('stream')
const selectedNodeId = ref<AgentNodeId>('chapters')

const runningRun = computed(() => props.aiRuns.find((run) => run.status === 'running'))
const runningProgress = computed(() => progressPayload(runningRun.value))
const activeNodeId = computed<AgentNodeId | undefined>(() => {
  const run = runningRun.value
  if (!run) return undefined

  if (run.task_type === 'chapter_analysis') return 'chapter_agent'
  if (run.task_type === 'story_elements') return 'card_agent'
  if (run.task_type === 'script_yaml_repair') return 'repair_agent'
  if (run.task_type !== 'script_yaml') return undefined

  const phase = String(runningProgress.value?.phase ?? '')
  if (phase === 'scene_planning') return 'scene_planner'
  if (phase === 'fragment_generation') return 'yaml_writer'
  if (phase === 'memory_update' || phase === 'chapter_completed') return 'memory_agent'
  if (phase === 'assemble') return 'validator'
  if (phase === 'finished') return 'script_result'
  return 'scene_planner'
})

const agentNodes: AgentNode[] = [
  { id: 'chapters', label: '章节入口', caption: '读取小说章节', x: 80, y: 190 },
  { id: 'chapter_agent', label: '章节分析', caption: '总结、人物、场景候选', x: 230, y: 95 },
  { id: 'card_agent', label: '抽取元素', caption: '调用卡片读写工具', x: 390, y: 95 },
  { id: 'card_store', label: '故事卡片库', caption: '角色、地点、事件、场景', x: 545, y: 190 },
  { id: 'scene_planner', label: '场景规划', caption: '逐章规划场次', x: 390, y: 315 },
  { id: 'yaml_writer', label: 'YAML 写作', caption: '写入剧本片段', x: 545, y: 315 },
  { id: 'memory_agent', label: '记忆更新', caption: '延续人物与情节', x: 700, y: 315 },
  { id: 'validator', label: '结构校验', caption: '检查 Schema 引用', x: 700, y: 190 },
  { id: 'repair_agent', label: '工具修复', caption: '局部改写错误节点', x: 855, y: 190 },
  { id: 'script_result', label: '剧本版本', caption: props.scriptVersionName ?? '等待保存', x: 1015, y: 190 },
]
const defaultAgentNode: AgentNode = agentNodes[0]!

const agentLinks: AgentLink[] = [
  { source: 'chapters', target: 'chapter_agent' },
  { source: 'chapter_agent', target: 'card_agent' },
  { source: 'card_agent', target: 'card_store' },
  { source: 'card_store', target: 'scene_planner' },
  { source: 'scene_planner', target: 'yaml_writer' },
  { source: 'yaml_writer', target: 'memory_agent' },
  { source: 'memory_agent', target: 'validator' },
  { source: 'validator', target: 'script_result' },
  { source: 'validator', target: 'repair_agent' },
  { source: 'repair_agent', target: 'script_result' },
]

const nodeDetails: Record<AgentNodeId, NodeDetail> = {
  chapters: {
    purpose: '把当前项目保存的小说章节作为后续 Agent 的入口数据。',
    input: '项目标题、章节列表、章节正文。',
    output: '可被章节分析、故事元素抽取和剧本生成复用的章节上下文。',
    note: '如果这里章节数不对，后续所有 AI 节点都会基于错误输入工作。',
  },
  chapter_agent: {
    purpose: '逐章总结正文，提取人物、地点、事件、冲突、对话候选和场景候选。',
    input: '单章正文、前文分析记忆。',
    output: '章节分析记录，后续故事卡片抽取会读取这些结构化摘要。',
    note: '如果角色在原文出现但这里漏掉，抽取元素 Agent 会再通过章节读取/搜索工具补查。',
  },
  card_agent: {
    purpose: '读取当前章节和已有卡片，用工具创建或修正角色、地点、事件和场景卡。',
    input: '当前章节全文、章节分析、已有故事卡片库。',
    output: '增量更新后的故事卡片。',
    note: '遇到未知角色或地点时，会先查章节证据，再补齐卡片，不直接重写整份结果。',
  },
  card_store: {
    purpose: '保存 Agent 维护后的故事卡片快照。',
    input: '角色卡、地点卡、事件卡、场景卡写入操作。',
    output: '当前项目的结构化故事资料库。',
    note: '剧本生成会优先依赖这里的卡片，而不是只依赖一次性提示词。',
  },
  scene_planner: {
    purpose: '根据章节分析和故事卡片，把每章拆成可拍摄的场景计划。',
    input: '当前章节、角色卡、地点卡、事件卡、已有场景卡。',
    output: '场景标题、地点、出场角色、戏剧目的和关键节拍。',
    note: '这个节点决定预演画布里每一场的结构。',
  },
  yaml_writer: {
    purpose: '把场景计划写成符合 Schema 的 YAML 剧本片段。',
    input: '单章场景计划、故事卡片、上一章记忆。',
    output: '当前章节的 scenes、shots、dialogue、actions 等 YAML 片段。',
    note: '现在是逐章写入，避免一次把长篇小说全部塞给模型。',
  },
  memory_agent: {
    purpose: '记录跨章节人物状态、关系变化和未解决事件。',
    input: '当前章节生成结果、已有剧本记忆。',
    output: '供下一章复用的连续性记忆。',
    note: '这是后续追加章节时能继续演化人物和剧情的关键。',
  },
  validator: {
    purpose: '检查 YAML Schema、角色/地点/事件 ID 引用和 shot 结构。',
    input: '已生成的 YAML 剧本片段和故事卡片库。',
    output: '通过的结构化 YAML，或需要修复的具体错误。',
    note: '校验失败不会悄悄吞掉，会把错误交给工具修复节点处理。',
  },
  repair_agent: {
    purpose: '读取错误位置，用工具局部修改 YAML 节点。',
    input: '校验错误、当前 YAML、故事卡片和章节上下文。',
    output: '修复后的 YAML 版本。',
    note: '它不是重新生成整份剧本，而是像 Codex 一样针对错误点改文件。',
  },
  script_result: {
    purpose: '保存最终可预览、可编辑、可导出的剧本版本。',
    input: '通过校验的 YAML 剧本。',
    output: '项目中的剧本版本记录。',
    note: '这里的版本会进入右侧剧本结果面板，用于预演和导出。',
  },
}

const runningPercent = computed(() => {
  const run = runningRun.value
  if (!run) return 0
  return runProgressPercent(run)
})

const runningMessage = computed(() => {
  const progress = runningProgress.value
  if (progress?.message) return String(progress.message)
  return runningRun.value ? `${taskLabel(runningRun.value.task_type)}运行中` : '暂无运行中的 Agent'
})

const currentToolMessage = computed(() => {
  const nodeId = activeNodeId.value
  if (!nodeId) return '等待新的 AI 任务启动。'

  const messages: Record<AgentNodeId, string> = {
    chapters: '读取项目章节。',
    chapter_agent: '章节分析 Agent 正在总结当前章节，并提取候选角色、地点和事件。',
    card_agent: '故事元素 Agent 正在读取已有卡片，并用工具补充或修改角色、地点、事件和场景。',
    card_store: '卡片库正在保存结构化故事元素。',
    scene_planner: '场景规划 Agent 正在根据章节卡片拆分场次。',
    yaml_writer: 'YAML 写作 Agent 正在写入当前章节的剧本片段。',
    memory_agent: '记忆 Agent 正在更新跨章节人物状态和情节连续性。',
    validator: '校验节点正在检查 YAML Schema、ID 引用和分镜结构。',
    repair_agent: '修复 Agent 正在读取错误位置，并用工具局部修改 YAML。',
    script_result: '剧本版本已经进入结果节点。',
  }
  return messages[nodeId]
})

const selectedNode = computed<AgentNode>(() => agentNodes.find((node) => node.id === selectedNodeId.value) ?? defaultAgentNode)
const selectedNodeDetail = computed(() => nodeDetails[selectedNode.value.id])
const selectedNodeStatus = computed(() => nodeStatus(selectedNode.value.id))

const streamMessages = computed<StreamMessage[]>(() => {
  const run = runningRun.value
  if (!run) return []
  return streamPayload(run).map((item, index) => ({
    id: String(item.id ?? `${run.id}-${index}`),
    type: String(item.type ?? 'message'),
    node: String(item.node ?? ''),
    title: String(item.title ?? streamEventLabel(String(item.type ?? 'message'))),
    content: String(item.content ?? ''),
    meta: streamMeta(item),
  }))
})

function selectNode(nodeId: AgentNodeId): void {
  selectedNodeId.value = nodeId
  sideTab.value = 'node'
}

function nodeStatus(nodeId: AgentNodeId): AgentNodeStatus {
  if (nodeId === activeNodeId.value) return 'running'
  if (isNodeSucceeded(nodeId)) return 'succeeded'
  if (nodeLatestFailed(nodeId)) return 'failed'
  return 'pending'
}

function isNodeSucceeded(nodeId: AgentNodeId): boolean {
  if (nodeId === 'chapters') return props.chapterCount > 0
  if (nodeId === 'chapter_agent') return hasSucceeded('chapter_analysis') || Boolean(props.storyElements)
  if (nodeId === 'card_agent' || nodeId === 'card_store') {
    return hasSucceeded('story_elements') || Boolean(props.storyElements)
  }
  if (['scene_planner', 'yaml_writer', 'memory_agent', 'validator', 'script_result'].includes(nodeId)) {
    return hasSucceeded('script_yaml') || Boolean(props.scriptVersionName)
  }
  if (nodeId === 'repair_agent') return hasSucceeded('script_yaml_repair')
  return false
}

function hasSucceeded(taskType: string): boolean {
  return props.aiRuns.some((run) => run.task_type === taskType && run.status === 'succeeded')
}

function nodeLatestFailed(nodeId: AgentNodeId): boolean {
  const taskType = nodeTaskType(nodeId)
  if (!taskType) return false
  return props.aiRuns.find((run) => run.task_type === taskType)?.status === 'failed'
}

function nodeTaskType(nodeId: AgentNodeId): string | undefined {
  if (nodeId === 'chapter_agent') return 'chapter_analysis'
  if (nodeId === 'card_agent' || nodeId === 'card_store') return 'story_elements'
  if (['scene_planner', 'yaml_writer', 'memory_agent', 'validator', 'script_result'].includes(nodeId)) {
    return 'script_yaml'
  }
  if (nodeId === 'repair_agent') return 'script_yaml_repair'
  return undefined
}

function nodeFill(status: AgentNodeStatus): string {
  const colors: Record<AgentNodeStatus, string> = {
    pending: '#e4e4e7',
    running: '#0284c7',
    succeeded: '#059669',
    failed: '#dc2626',
  }
  return colors[status]
}

function nodeStroke(status: AgentNodeStatus): string {
  const colors: Record<AgentNodeStatus, string> = {
    pending: '#f4f4f5',
    running: '#bae6fd',
    succeeded: '#bbf7d0',
    failed: '#fecaca',
  }
  return colors[status]
}

function linkStroke(link: AgentLink): string {
  const sourceStatus = nodeStatus(link.source)
  const targetStatus = nodeStatus(link.target)
  if (sourceStatus === 'failed' || targetStatus === 'failed') return '#fecaca'
  if (targetStatus === 'running') return '#7dd3fc'
  if (sourceStatus === 'succeeded' && targetStatus === 'succeeded') return '#a7f3d0'
  return '#e4e4e7'
}

function statusIcon(status: AgentNodeStatus) {
  if (status === 'running') return Loader2
  if (status === 'succeeded') return CheckCircle2
  if (status === 'failed') return TriangleAlert
  return Circle
}

function statusLabel(status: AgentNodeStatus): string {
  const labels: Record<AgentNodeStatus, string> = {
    pending: '等待',
    running: '运行中',
    succeeded: '完成',
    failed: '失败',
  }
  return labels[status]
}

function progressPayload(run?: AIRun): Record<string, unknown> | undefined {
  const progress = run?.output_payload?.progress
  return isRecord(progress) ? progress : undefined
}

function runProgressPercent(run: AIRun): number {
  if (run.status === 'succeeded') return 100
  if (run.status === 'failed') return 100

  const progress = progressPayload(run)
  if (!progress) return 8

  const chapterTotal = Math.max(1, Number(progress.chapter_total ?? props.chapterCount ?? 1))
  const completedChapters = Math.max(0, Number(progress.completed_chapters ?? 0))
  const chapterIndex = Math.max(1, Number(progress.chapter_index ?? 1))
  const phase = String(progress.phase ?? '')
  const stageWeight = phaseWeight(phase)
  const rawPercent = Math.max(completedChapters, chapterIndex - 1 + stageWeight) / chapterTotal
  return Math.min(100, Math.max(0, Math.round(rawPercent * 100)))
}

function phaseWeight(phase: string): number {
  const weights: Record<string, number> = {
    chapter_analysis: 0.35,
    chapter_processing: 0.35,
    scene_planning: 0.22,
    fragment_generation: 0.52,
    memory_update: 0.78,
    chapter_completed: 1,
    assemble: 1,
    finished: 1,
  }
  return weights[phase] ?? 0.2
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function streamPayload(run: AIRun): Record<string, unknown>[] {
  const stream = run.output_payload?.stream
  if (!Array.isArray(stream)) return []
  return stream.filter(isRecord)
}

function streamMeta(item: Record<string, unknown>): string {
  const node = streamNodeLabel(String(item.node ?? ''))
  const createdAt = typeof item.created_at === 'string' ? formatTime(item.created_at) : ''
  return [node, createdAt].filter(Boolean).join(' · ')
}

function streamNodeLabel(node: string): string {
  const labels: Record<string, string> = {
    chapter_analysis: '章节分析',
    story_cards: '故事卡片',
    script_yaml: '剧本生成',
    scene_planning: '场景规划',
    yaml_writer: 'YAML 写作',
    script_memory: '记忆更新',
    yaml_repair: 'YAML 修复',
  }
  return labels[node] ?? node
}

function streamEventLabel(type: string): string {
  const labels: Record<string, string> = {
    model_start: '模型请求',
    assistant: '模型输出',
    tool_call: '工具调用',
    tool_result: '工具结果',
    tool_error: '工具错误',
    stage: '阶段',
    message: '消息',
  }
  return labels[type] ?? type
}

function streamEventClass(type: string): string {
  const classes: Record<string, string> = {
    assistant: 'border-sky-200 bg-sky-50/70 text-sky-950',
    tool_call: 'border-violet-200 bg-violet-50/70 text-violet-950',
    tool_result: 'border-emerald-200 bg-emerald-50/70 text-emerald-950',
    tool_error: 'border-red-200 bg-red-50/80 text-red-950',
    stage: 'border-zinc-200 bg-zinc-50 text-zinc-950',
    model_start: 'border-zinc-200 bg-zinc-50 text-zinc-950',
  }
  return classes[type] ?? 'border-zinc-200 bg-muted/20 text-foreground'
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent
      class="flex h-[min(820px,calc(100vh-2rem))] !w-[min(1280px,calc(100vw-2rem))] !max-w-none flex-col overflow-hidden p-0"
    >
      <DialogHeader class="shrink-0 border-b px-5 py-4">
        <div class="flex items-start justify-between gap-3 pr-10">
          <div>
            <DialogTitle class="flex items-center gap-2 text-base">
              <GitBranch class="size-4" />
              Agent 执行画布
            </DialogTitle>
            <DialogDescription>观察章节分析、卡片抽取、剧本生成和修复节点的实时流。</DialogDescription>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <Badge v-if="runningRun" variant="secondary">运行中</Badge>
            <Badge v-else variant="outline">空闲</Badge>
            <Badge variant="outline">{{ aiRuns.length }} 条记录</Badge>
          </div>
        </div>
      </DialogHeader>

      <div class="grid min-h-0 flex-1 gap-0 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div class="min-h-0 overflow-hidden bg-muted/20 p-4">
          <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border bg-background">
            <div class="shrink-0 border-b px-4 py-3">
              <div class="flex items-center justify-between gap-3">
                <div>
                  <p class="text-sm font-medium">当前工具流</p>
                  <p class="mt-1 text-xs text-muted-foreground">{{ currentToolMessage }}</p>
                </div>
                <div class="shrink-0 text-right">
                  <p class="text-sm font-medium">{{ runningPercent }}%</p>
                  <p class="mt-1 text-xs text-muted-foreground">{{ runningMessage }}</p>
                </div>
              </div>
              <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  class="h-full rounded-full bg-sky-600 transition-all duration-500"
                  :style="{ width: `${runningPercent}%` }"
                />
              </div>
            </div>

            <div class="min-h-0 flex-1 overflow-hidden p-4">
              <svg class="h-full min-h-[440px] w-full rounded-lg border bg-white" viewBox="0 0 1100 430">
                <defs>
                  <marker
                    id="agent-arrow"
                    markerHeight="8"
                    markerWidth="8"
                    orient="auto"
                    refX="7"
                    refY="4"
                  >
                    <path d="M0,0 L8,4 L0,8 Z" fill="#d4d4d8" />
                  </marker>
                </defs>

                <g>
                  <line
                    v-for="link in agentLinks"
                    :key="`${link.source}-${link.target}`"
                    :x1="agentNodes.find((node) => node.id === link.source)?.x"
                    :y1="agentNodes.find((node) => node.id === link.source)?.y"
                    :x2="agentNodes.find((node) => node.id === link.target)?.x"
                    :y2="agentNodes.find((node) => node.id === link.target)?.y"
                    :stroke="linkStroke(link)"
                    stroke-width="3"
                    stroke-linecap="round"
                    marker-end="url(#agent-arrow)"
                  />
                </g>

                <g
                  v-for="node in agentNodes"
                  :key="node.id"
                  :transform="`translate(${node.x}, ${node.y})`"
                  class="cursor-pointer outline-none"
                  role="button"
                  tabindex="0"
                  @click="selectNode(node.id)"
                  @keydown.enter="selectNode(node.id)"
                  @keydown.space.prevent="selectNode(node.id)"
                >
                  <circle
                    v-if="selectedNodeId === node.id"
                    r="39"
                    fill="none"
                    stroke="#18181b"
                    stroke-width="2"
                    stroke-dasharray="4 5"
                  />
                  <circle
                    v-if="nodeStatus(node.id) === 'running'"
                    r="40"
                    :fill="nodeFill(nodeStatus(node.id))"
                    opacity="0.14"
                  >
                    <animate attributeName="r" values="34;48;34" dur="1.8s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.2;0.05;0.2" dur="1.8s" repeatCount="indefinite" />
                  </circle>
                  <circle
                    r="28"
                    :fill="nodeFill(nodeStatus(node.id))"
                    :stroke="nodeStroke(nodeStatus(node.id))"
                    stroke-width="6"
                  />
                  <foreignObject x="-11" y="-11" width="22" height="22">
                    <component
                      :is="statusIcon(nodeStatus(node.id))"
                      class="size-5 text-white"
                      :class="nodeStatus(node.id) === 'running' ? 'animate-spin' : ''"
                    />
                  </foreignObject>
                  <text
                    y="48"
                    text-anchor="middle"
                    class="fill-zinc-900 text-[14px] font-semibold"
                  >
                    {{ node.label }}
                  </text>
                  <text
                    y="66"
                    text-anchor="middle"
                    class="fill-zinc-500 text-[11px]"
                  >
                    {{ node.caption }}
                  </text>
                  <text
                    y="-38"
                    text-anchor="middle"
                    class="fill-zinc-500 text-[11px]"
                  >
                    {{ statusLabel(nodeStatus(node.id)) }}
                  </text>
                </g>
              </svg>
            </div>
          </div>
        </div>

        <aside class="min-h-0 border-l bg-background p-4">
          <div class="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-4">
            <div class="grid grid-cols-2 gap-2">
              <div class="rounded-lg border bg-muted/20 p-3">
                <div class="flex items-center gap-2 text-xs text-muted-foreground">
                  <Activity class="size-3.5" />
                  章节
                </div>
                <p class="mt-1 text-xl font-semibold">{{ chapterCount }}</p>
              </div>
              <div class="rounded-lg border bg-muted/20 p-3">
                <div class="flex items-center gap-2 text-xs text-muted-foreground">
                  <Database class="size-3.5" />
                  卡片
                </div>
                <p class="mt-1 text-xl font-semibold">
                  {{
                    storyElements
                      ? storyElements.characters.length + storyElements.locations.length + storyElements.events.length + storyElements.scenes.length
                      : 0
                  }}
                </p>
              </div>
              <div class="rounded-lg border bg-muted/20 p-3">
                <div class="flex items-center gap-2 text-xs text-muted-foreground">
                  <FileCode2 class="size-3.5" />
                  版本
                </div>
                <p class="mt-1 truncate text-sm font-semibold">{{ scriptVersionName ?? '无' }}</p>
              </div>
              <div class="rounded-lg border bg-muted/20 p-3">
                <div class="flex items-center gap-2 text-xs text-muted-foreground">
                  <FileCheck2 class="size-3.5" />
                  状态
                </div>
                <p class="mt-1 truncate text-sm font-semibold">{{ runningRun ? '运行中' : '空闲' }}</p>
              </div>
            </div>

            <Tabs v-model="sideTab" class="flex h-full min-h-0 flex-col gap-2">
              <TabsList class="!grid !h-8 !w-full !shrink-0 grid-cols-2">
                <TabsTrigger value="stream" class="!h-7 !min-h-0 !py-0">实时流</TabsTrigger>
                <TabsTrigger value="node" class="!h-7 !min-h-0 !py-0">节点详情</TabsTrigger>
              </TabsList>

              <TabsContent value="stream" class="min-h-0 flex-1 overflow-hidden">
                <div class="mb-2">
                  <div class="flex items-center gap-2 text-sm font-medium">
                    <Sparkles class="size-4" />
                    Agent 消息
                  </div>
                  <p class="mt-1 text-xs leading-5 text-muted-foreground">
                    展示模型可见输出和工具调用，不展示隐藏思考。
                  </p>
                </div>
                <ScrollArea class="h-[calc(100%-3.25rem)] pr-2">
                  <div
                    v-if="!runningRun"
                    class="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
                  >
                    当前没有运行中的 Agent。
                  </div>
                  <div
                    v-else-if="streamMessages.length === 0"
                    class="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
                  >
                    等待模型输出。
                  </div>
                  <div v-else class="space-y-2">
                    <div
                      v-for="message in streamMessages"
                      :key="message.id"
                      class="rounded-lg border p-3"
                      :class="streamEventClass(message.type)"
                    >
                      <div class="flex items-center justify-between gap-2">
                        <div class="min-w-0">
                          <p class="truncate text-xs font-medium">{{ message.title || streamEventLabel(message.type) }}</p>
                          <p class="mt-0.5 truncate text-[11px] opacity-70">{{ message.meta }}</p>
                        </div>
                        <span class="shrink-0 rounded border bg-background/70 px-1.5 py-0.5 text-[11px] opacity-80">
                          {{ streamEventLabel(message.type) }}
                        </span>
                      </div>
                      <p class="mt-2 whitespace-pre-wrap break-words text-sm leading-6">{{ message.content }}</p>
                    </div>
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="node" class="min-h-0 flex-1 overflow-hidden">
                <div class="mb-2">
                  <div class="flex items-center justify-between gap-2">
                    <div class="min-w-0">
                      <div class="flex items-center gap-2 text-sm font-medium">
                        <GitBranch class="size-4" />
                        {{ selectedNode.label }}
                      </div>
                      <p class="mt-1 text-xs leading-5 text-muted-foreground">{{ selectedNode.caption }}</p>
                    </div>
                    <span class="shrink-0 rounded border px-2 py-0.5 text-xs">
                      {{ statusLabel(selectedNodeStatus) }}
                    </span>
                  </div>
                </div>

                <ScrollArea class="h-[calc(100%-3.25rem)] pr-2">
                  <div class="space-y-2">
                    <section class="rounded-lg border bg-muted/20 p-3">
                      <p class="text-xs font-medium text-muted-foreground">节点作用</p>
                      <p class="mt-2 text-sm leading-6">{{ selectedNodeDetail.purpose }}</p>
                    </section>
                    <section class="rounded-lg border bg-muted/20 p-3">
                      <p class="text-xs font-medium text-muted-foreground">读取内容</p>
                      <p class="mt-2 text-sm leading-6">{{ selectedNodeDetail.input }}</p>
                    </section>
                    <section class="rounded-lg border bg-muted/20 p-3">
                      <p class="text-xs font-medium text-muted-foreground">写入结果</p>
                      <p class="mt-2 text-sm leading-6">{{ selectedNodeDetail.output }}</p>
                    </section>
                    <section class="rounded-lg border bg-muted/20 p-3">
                      <p class="text-xs font-medium text-muted-foreground">观察重点</p>
                      <p class="mt-2 text-sm leading-6">{{ selectedNodeDetail.note }}</p>
                    </section>
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </div>
        </aside>
      </div>
    </DialogContent>
  </Dialog>
</template>
