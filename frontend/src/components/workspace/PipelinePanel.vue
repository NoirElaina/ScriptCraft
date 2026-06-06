<script setup lang="ts">
import { computed } from 'vue'
import {
  CheckCircle2,
  Clock,
  GitBranch,
  Loader2,
  MapPin,
  RefreshCw,
  Sparkles,
  Users,
} from '@lucide/vue'

import type { AIRun, StoryElementsSnapshot } from '@/api/projects'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatTime, runStatusClass, taskLabel } from '@/lib/workspace-formatters'
import ScriptYamlPanel from './ScriptYamlPanel.vue'

interface AITaskProgress {
  phase?: string
  message?: string
  chapter_index?: number
  chapter_total?: number
  completed_chapters?: number
  current_chapter_title?: string
  character_count?: number
  location_count?: number
  event_count?: number
  fragment_count?: number
}

const props = defineProps<{
  chaptersLength: number
  chapterAnalysesLength: number
  storyElements?: StoryElementsSnapshot
  scriptYaml: string
  projectTitle: string
  scriptVersionName?: string
  aiRuns: AIRun[]
  isLoadingWorkspace: boolean
  isAnalyzingChapters: boolean
  isExtracting: boolean
  isGeneratingYaml: boolean
  isAiTaskRunning: boolean
  isSavingYaml: boolean
}>()

const activeFlowTab = defineModel<string>('activeFlowTab', { required: true })
const activeYamlTab = defineModel<string>('activeYamlTab', { required: true })

const storyElementsProgress = computed(() => taskProgress('story_elements'))
const scriptYamlProgress = computed(() => taskProgress('script_yaml'))
const chapterAnalysisProgressPercent = computed(() => {
  if (props.chaptersLength === 0) return 0
  if (props.chapterAnalysesLength >= props.chaptersLength) return 100

  const partialChapter = props.isAnalyzingChapters ? 0.35 : 0
  return Math.min(100, Math.round(((props.chapterAnalysesLength + partialChapter) / props.chaptersLength) * 100))
})
const chapterAnalysisProgressMessage = computed(() => {
  if (props.chapterAnalysesLength >= props.chaptersLength && props.chaptersLength >= 3) {
    return '全部章节分析完成'
  }
  const currentChapter = Math.min(props.chapterAnalysesLength + 1, props.chaptersLength)
  return `正在分析第 ${currentChapter} 章：${props.chapterAnalysesLength}/${props.chaptersLength}`
})
const shouldShowChapterAnalysisProgress = computed(() => {
  return props.isAnalyzingChapters || props.chapterAnalysesLength > 0
})
const storyElementsProgressPercent = computed(() => progressPercent(storyElementsProgress.value, 'story_elements'))
const scriptYamlProgressPercent = computed(() => progressPercent(scriptYamlProgress.value, 'script_yaml'))

const emit = defineEmits<{
  refresh: []
  analyzeChapters: []
  extractStoryElements: []
  generateScriptYaml: []
  saveScriptYaml: [yamlContent: string, versionName: string]
}>()

function taskProgress(taskType: string): AITaskProgress | undefined {
  const run = props.aiRuns.find((item) => item.task_type === taskType && item.status === 'running')
  const payload = run?.output_payload
  if (!isRecord(payload)) return undefined

  const progress = payload.progress
  return isRecord(progress) ? (progress as AITaskProgress) : undefined
}

function progressPercent(progress: AITaskProgress | undefined, taskType: 'story_elements' | 'script_yaml'): number {
  if (!progress?.chapter_total) return 0
  const completed = Math.max(0, Number(progress.completed_chapters ?? 0))
  const chapterIndex = Math.max(1, Number(progress.chapter_index ?? 1))
  const phaseWeight = taskType === 'script_yaml'
    ? scriptYamlPhaseWeight(progress.phase)
    : storyElementsPhaseWeight(progress.phase)
  const currentChapterProgress = Math.max(0, chapterIndex - 1 + phaseWeight)
  const rawPercent = Math.max(completed, currentChapterProgress) / progress.chapter_total
  return Math.min(100, Math.max(0, Math.round(rawPercent * 100)))
}

function storyElementsPhaseWeight(phase?: string): number {
  if (phase === 'chapter_completed' || phase === 'finished') return 1
  if (phase === 'chapter_processing') return 0.35
  return 0
}

function scriptYamlPhaseWeight(phase?: string): number {
  if (phase === 'fragment_generation') return 0.5
  if (phase === 'memory_update') return 0.8
  if (phase === 'chapter_completed' || phase === 'finished') return 1
  if (phase === 'assemble') return 1
  if (phase === 'scene_planning') return 0.2
  return 0
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
</script>

<template>
  <Card class="flex min-h-0 flex-col overflow-hidden">
    <CardHeader class="shrink-0">
      <div class="flex items-start justify-between gap-3">
        <div>
          <CardTitle class="text-base">剧本生成流程</CardTitle>
          <CardDescription>AI 结果会写回当前项目。</CardDescription>
        </div>
        <Button size="sm" variant="outline" :disabled="isLoadingWorkspace" @click="emit('refresh')">
          <Loader2 v-if="isLoadingWorkspace" class="size-4 animate-spin" />
          <RefreshCw v-else class="size-4" />
        </Button>
      </div>
    </CardHeader>

    <CardContent class="min-h-0 flex-1 overflow-hidden">
      <Tabs v-model="activeFlowTab" class="flex h-full min-h-0 flex-col">
        <TabsList class="grid w-full shrink-0 grid-cols-2">
          <TabsTrigger value="pipeline">流程</TabsTrigger>
          <TabsTrigger value="yaml">YAML</TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline" class="mt-4 min-h-0 flex-1 overflow-hidden">
          <ScrollArea class="h-full pr-3">
            <div class="space-y-3">
              <div class="rounded-lg border bg-background p-4">
                <div class="flex items-center gap-2 text-sm font-medium">
                  <CheckCircle2 v-if="chaptersLength >= 3" class="size-4 text-emerald-600" />
                  <span v-else class="size-4 rounded-full border" />
                  章节解析
                </div>
                <p class="mt-2 text-sm text-muted-foreground">已保存 {{ chaptersLength }} 个章节。</p>
              </div>

              <div class="rounded-lg border bg-background p-4">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="flex items-center gap-2 text-sm font-medium">
                      <CheckCircle2
                        v-if="chapterAnalysesLength >= chaptersLength && chaptersLength >= 3"
                        class="size-4 text-emerald-600"
                      />
                      <span v-else class="size-4 rounded-full border" />
                      AI 章节分析
                    </div>
                    <p class="mt-2 text-sm text-muted-foreground">
                      已分析 {{ chapterAnalysesLength }} / {{ chaptersLength }} 章，后续步骤复用结构化结果。
                    </p>
                  </div>
                  <Button
                    :disabled="isAiTaskRunning || chaptersLength < 3"
                    class="shrink-0"
                    @click="emit('analyzeChapters')"
                  >
                    <Loader2 v-if="isAnalyzingChapters" class="size-4 animate-spin" />
                    <Sparkles v-else class="size-4" />
                    分析
                  </Button>
                </div>
                <div v-if="shouldShowChapterAnalysisProgress" class="mt-3 rounded-md bg-muted/50 p-3">
                  <div class="flex items-start justify-between gap-3 text-xs">
                    <span class="min-w-0 flex-1 leading-5 text-muted-foreground">
                      {{ chapterAnalysisProgressMessage }}
                    </span>
                    <span class="shrink-0 font-medium">{{ chapterAnalysisProgressPercent }}%</span>
                  </div>
                  <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-background">
                    <div
                      class="h-full rounded-full bg-sky-600"
                      :style="{ width: `${chapterAnalysisProgressPercent}%` }"
                    />
                  </div>
                  <p class="mt-2 text-xs text-muted-foreground">
                    已完成 {{ chapterAnalysesLength }} / {{ chaptersLength }} 章，
                    后续故事元素和剧本生成会复用章节结构化结果。
                  </p>
                </div>
              </div>

              <div class="rounded-lg border bg-background p-4">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="flex items-center gap-2 text-sm font-medium">
                      <CheckCircle2 v-if="storyElements" class="size-4 text-emerald-600" />
                      <span v-else class="size-4 rounded-full border" />
                      AI 故事元素抽取
                    </div>
                    <p class="mt-2 text-sm text-muted-foreground">
                      角色 {{ storyElements?.characters.length ?? 0 }} 个，地点
                      {{ storyElements?.locations.length ?? 0 }} 个，事件
                      {{ storyElements?.events.length ?? 0 }} 个。
                    </p>
                  </div>
                  <Button
                    :disabled="isAiTaskRunning || chapterAnalysesLength < chaptersLength || chaptersLength < 3"
                    class="shrink-0"
                    @click="emit('extractStoryElements')"
                  >
                    <Loader2 v-if="isExtracting" class="size-4 animate-spin" />
                    <Sparkles v-else class="size-4" />
                    抽取
                  </Button>
                </div>
                <div v-if="storyElementsProgress" class="mt-3 rounded-md bg-muted/50 p-3">
                  <div class="flex items-start justify-between gap-3 text-xs">
                    <span class="min-w-0 flex-1 leading-5 text-muted-foreground">
                      {{ storyElementsProgress.message }}
                    </span>
                    <span class="shrink-0 font-medium">{{ storyElementsProgressPercent }}%</span>
                  </div>
                  <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-background">
                    <div
                      class="h-full rounded-full bg-emerald-600"
                      :style="{ width: `${storyElementsProgressPercent}%` }"
                    />
                  </div>
                  <p class="mt-2 text-xs text-muted-foreground">
                    已完成 {{ storyElementsProgress.completed_chapters ?? 0 }} /
                    {{ storyElementsProgress.chapter_total ?? chaptersLength }} 章，
                    当前累计角色 {{ storyElementsProgress.character_count ?? 0 }} 个，地点
                    {{ storyElementsProgress.location_count ?? 0 }} 个，事件
                    {{ storyElementsProgress.event_count ?? 0 }} 个。
                  </p>
                </div>
              </div>

              <div class="rounded-lg border bg-background p-4">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="flex items-center gap-2 text-sm font-medium">
                      <CheckCircle2 v-if="scriptYaml" class="size-4 text-emerald-600" />
                      <span v-else class="size-4 rounded-full border" />
                      AI 剧本 YAML 生成
                    </div>
                    <p class="mt-2 text-sm text-muted-foreground">
                      当前版本：{{ props.scriptVersionName ?? '无' }}
                    </p>
                  </div>
                  <Button
                    :disabled="isAiTaskRunning || !storyElements"
                    class="shrink-0"
                    @click="emit('generateScriptYaml')"
                  >
                    <Loader2 v-if="isGeneratingYaml" class="size-4 animate-spin" />
                    <Sparkles v-else class="size-4" />
                    生成
                  </Button>
                </div>
                <div v-if="scriptYamlProgress" class="mt-3 rounded-md bg-muted/50 p-3">
                  <div class="flex items-start justify-between gap-3 text-xs">
                    <span class="min-w-0 flex-1 leading-5 text-muted-foreground">
                      {{ scriptYamlProgress.message }}
                    </span>
                    <span class="shrink-0 font-medium">{{ scriptYamlProgressPercent }}%</span>
                  </div>
                  <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-background">
                    <div
                      class="h-full rounded-full bg-sky-600"
                      :style="{ width: `${scriptYamlProgressPercent}%` }"
                    />
                  </div>
                  <p class="mt-2 text-xs text-muted-foreground">
                    已完成 {{ scriptYamlProgress.completed_chapters ?? 0 }} /
                    {{ scriptYamlProgress.chapter_total ?? chaptersLength }} 章，
                    已生成片段 {{ scriptYamlProgress.fragment_count ?? 0 }} 个。
                  </p>
                </div>
              </div>

              <div v-if="storyElements" class="space-y-3">
                <div class="rounded-lg border bg-background p-4">
                  <div class="flex items-center gap-2 text-sm font-medium">
                    <Users class="size-4" />
                    角色
                  </div>
                  <div class="mt-3 space-y-2">
                    <div
                      v-for="character in storyElements.characters"
                      :key="character.id"
                      class="rounded-md bg-muted/60 p-3"
                    >
                      <p class="text-sm font-medium">{{ character.name }}</p>
                      <p class="mt-1 text-xs leading-5 text-muted-foreground">
                        {{ character.description }}
                      </p>
                    </div>
                  </div>
                </div>

                <div class="rounded-lg border bg-background p-4">
                  <div class="flex items-center gap-2 text-sm font-medium">
                    <MapPin class="size-4" />
                    地点
                  </div>
                  <div class="mt-3 space-y-2">
                    <div
                      v-for="location in storyElements.locations"
                      :key="location.id"
                      class="rounded-md bg-muted/60 p-3"
                    >
                      <p class="text-sm font-medium">{{ location.name }}</p>
                      <p class="mt-1 text-xs leading-5 text-muted-foreground">
                        {{ location.description }}
                      </p>
                    </div>
                  </div>
                </div>

                <div class="rounded-lg border bg-background p-4">
                  <div class="flex items-center gap-2 text-sm font-medium">
                    <GitBranch class="size-4" />
                    事件
                  </div>
                  <div class="mt-3 space-y-2">
                    <div
                      v-for="event in storyElements.events"
                      :key="event.id"
                      class="rounded-md bg-muted/60 p-3"
                    >
                      <p class="text-sm font-medium">{{ event.source_chapter }}</p>
                      <p class="mt-1 text-xs leading-5 text-muted-foreground">
                        {{ event.summary }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <Separator />

              <div class="space-y-2">
                <div class="flex items-center gap-2 text-sm font-medium">
                  <Clock class="size-4" />
                  AI 运行记录
                </div>
                <div v-if="aiRuns.length === 0" class="text-sm text-muted-foreground">
                  暂无运行记录。
                </div>
                <div v-for="run in aiRuns" :key="run.id" class="rounded-lg border bg-background p-3">
                  <div class="flex items-center justify-between gap-2">
                    <p class="text-sm font-medium">{{ taskLabel(run.task_type) }}</p>
                    <span class="rounded border px-2 py-0.5 text-xs" :class="runStatusClass(run.status)">
                      {{ run.status }}
                    </span>
                  </div>
                  <p class="mt-1 text-xs text-muted-foreground">
                    {{ formatTime(run.created_at) }}
                    <span v-if="run.duration_ms !== null"> · {{ run.duration_ms }}ms</span>
                  </p>
                  <p v-if="run.error_message" class="mt-2 text-xs leading-5 text-destructive">
                    {{ run.error_message }}
                  </p>
                </div>
              </div>
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="yaml" class="mt-4 min-h-0 flex-1">
          <ScriptYamlPanel
            v-model:active-yaml-tab="activeYamlTab"
            :script-yaml="scriptYaml"
            :project-title="projectTitle"
            :script-version-name="scriptVersionName"
            :has-story-elements="Boolean(storyElements) && !isAiTaskRunning"
            :is-generating-yaml="isGeneratingYaml"
            :is-saving-yaml="isSavingYaml"
            @generate="emit('generateScriptYaml')"
            @save="(yamlContent, versionName) => emit('saveScriptYaml', yamlContent, versionName)"
          />
        </TabsContent>
      </Tabs>
    </CardContent>
  </Card>
</template>
