<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  BookOpen,
  Clapperboard,
  FileText,
  GitBranch,
  Loader2,
  MessageSquareText,
  Sparkles,
  Users,
} from '@lucide/vue'

import type { AIRun, ChapterAnalysis, StoryElementsSnapshot } from '@/api/projects'
import type { Chapter } from '@/api/chapters'
import AgentFlowDialog from '@/components/workspace/AgentFlowDialog.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { normalizeNovelText } from '@/lib/novel-text'

const props = defineProps<{
  chapters: Chapter[]
  chapterAnalyses: ChapterAnalysis[]
  chapterCoverageLabel: string
  storyElements?: StoryElementsSnapshot
  scriptVersionName?: string
  aiRuns: AIRun[]
  isAnalyzingChapters: boolean
  isExtracting: boolean
  isGeneratingYaml: boolean
  isAiTaskRunning: boolean
}>()

const selectedChapterId = defineModel<string | undefined>('selectedChapterId')
const isAgentFlowOpen = ref(false)

const emit = defineEmits<{
  openNovelInput: []
  analyzeChapters: []
  extractStoryElements: []
  generateScriptYaml: []
}>()

const selectedChapter = computed(() => {
  return (
    props.chapters.find((chapter) => chapter.id === selectedChapterId.value) ?? props.chapters[0]
  )
})

const selectedChapterContent = computed(() => {
  return selectedChapter.value ? normalizeNovelText(selectedChapter.value.content) : ''
})

const selectedChapterAnalysis = computed(() => {
  if (!selectedChapter.value) return undefined
  return props.chapterAnalyses.find((analysis) => analysis.chapter_key === selectedChapter.value?.id)
})

const analyzedChapterIds = computed(() => {
  return new Set(props.chapterAnalyses.map((analysis) => analysis.chapter_key))
})

const pendingChapterAnalysisCount = computed(() => {
  return props.chapters.filter((chapter) => !analyzedChapterIds.value.has(chapter.id)).length
})

const runningAiRun = computed(() => {
  return props.aiRuns.find((run) => run.status === 'running')
})

const runningProgress = computed(() => {
  const progress = runningAiRun.value?.output_payload?.progress
  return isRecord(progress) ? progress : undefined
})

const runningProgressPercent = computed(() => {
  const progress = runningProgress.value
  if (!progress) return 0

  const chapterTotal = Number(progress.chapter_total ?? props.chapters.length)
  if (!chapterTotal) return 0

  const completedChapters = Math.max(0, Number(progress.completed_chapters ?? 0))
  const chapterIndex = Math.max(1, Number(progress.chapter_index ?? 1))
  const currentWeight = progress.phase === 'chapter_completed' || progress.phase === 'finished' ? 1 : 0.35
  const rawPercent = Math.max(completedChapters, chapterIndex - 1 + currentWeight) / chapterTotal

  return Math.min(100, Math.max(0, Math.round(rawPercent * 100)))
})

const runningMessage = computed(() => {
  const progress = runningProgress.value
  if (!progress) return taskLabel(runningAiRun.value?.task_type)
  return String(progress.message ?? taskLabel(runningAiRun.value?.task_type))
})

const storyElementsLabel = computed(() => {
  if (!props.storyElements) return '元素未抽取'
  return `角色 ${props.storyElements.characters.length} / 地点 ${props.storyElements.locations.length} / 事件 ${props.storyElements.events.length} / 场景 ${props.storyElements.scenes.length}`
})

function canAnalyzeChapters(): boolean {
  return !props.isAiTaskRunning && props.chapters.length > 0 && pendingChapterAnalysisCount.value > 0
}

function canExtractStoryElements(): boolean {
  return (
    !props.isAiTaskRunning &&
    props.chapters.length > 0 &&
    props.chapterAnalyses.length >= props.chapters.length
  )
}

function canGenerateScriptYaml(): boolean {
  return !props.isAiTaskRunning && Boolean(props.storyElements)
}

function taskLabel(taskType?: string): string {
  const labels: Record<string, string> = {
    chapter_analysis: 'AI 章节分析',
    story_elements: 'AI 故事元素抽取',
    script_yaml: 'AI 剧本生成',
  }
  return taskType ? labels[taskType] ?? taskType : 'AI 任务'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isChapterAnalyzed(chapter: Chapter): boolean {
  return analyzedChapterIds.value.has(chapter.id)
}
</script>

<template>
  <Card class="flex min-h-0 flex-col overflow-hidden">
    <CardHeader class="shrink-0">
      <div class="flex items-start justify-between gap-3">
        <div>
          <CardTitle class="flex items-center gap-2 text-base">
            <BookOpen class="size-4" />
            项目章节
          </CardTitle>
          <CardDescription>章节内容来自当前项目的数据库记录。</CardDescription>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <Badge :variant="chapters.length > 0 ? 'default' : 'secondary'">
            {{ chapterCoverageLabel }}
          </Badge>
          <Button size="sm" variant="outline" @click="emit('openNovelInput')">
            <FileText class="size-4" />
            小说输入
          </Button>
        </div>
      </div>

      <div class="mt-3 space-y-3">
        <div class="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" :disabled="!canAnalyzeChapters()" @click="emit('analyzeChapters')">
            <Loader2 v-if="isAnalyzingChapters" class="size-4 animate-spin" />
            <Sparkles v-else class="size-4" />
            章节分析
          </Button>
          <Button size="sm" variant="outline" :disabled="!canExtractStoryElements()" @click="emit('extractStoryElements')">
            <Loader2 v-if="isExtracting" class="size-4 animate-spin" />
            <Sparkles v-else class="size-4" />
            抽取元素
          </Button>
          <Button size="sm" :disabled="!canGenerateScriptYaml()" @click="emit('generateScriptYaml')">
            <Loader2 v-if="isGeneratingYaml" class="size-4 animate-spin" />
            <Sparkles v-else class="size-4" />
            生成剧本
          </Button>
          <Button
            size="sm"
            variant="outline"
            title="查看 Agent 实时流"
            @click="isAgentFlowOpen = true"
          >
            <GitBranch class="size-4" />
          </Button>
        </div>

        <div class="flex flex-wrap gap-2">
          <Badge variant="outline">章节分析 {{ chapterAnalyses.length }}/{{ chapters.length }}</Badge>
          <Badge variant="outline">{{ storyElementsLabel }}</Badge>
          <Badge variant="outline">{{ scriptVersionName ?? '无剧本版本' }}</Badge>
        </div>

        <div v-if="runningAiRun" class="rounded-md bg-muted/50 p-3">
          <div class="flex items-start justify-between gap-3 text-xs">
            <span class="min-w-0 flex-1 leading-5 text-muted-foreground">{{ runningMessage }}</span>
            <span class="shrink-0 font-medium">{{ runningProgressPercent }}%</span>
          </div>
          <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-background">
            <div
              class="h-full rounded-full bg-sky-600"
              :style="{ width: `${runningProgressPercent}%` }"
            />
          </div>
        </div>
      </div>
    </CardHeader>
    <CardContent
      class="grid min-h-0 flex-1 gap-4 overflow-hidden lg:grid-cols-[180px_minmax(0,1fr)]"
    >
      <div class="flex min-h-0 flex-col rounded-lg border bg-background">
        <div class="shrink-0 flex items-center justify-between border-b px-3 py-2">
          <span class="text-sm font-medium">章节列表</span>
          <Badge variant="outline">{{ chapters.length }} 章</Badge>
        </div>
        <ScrollArea class="min-h-0 flex-1">
          <div v-if="chapters.length === 0" class="p-4 text-sm text-muted-foreground">
            还没有保存章节。
          </div>
          <button
            v-for="chapter in chapters"
            :key="chapter.id"
            class="flex w-full flex-col items-start gap-1 border-b px-3 py-3 text-left transition hover:bg-muted/60"
            :class="chapter.id === selectedChapter?.id ? 'bg-muted' : ''"
            @click="selectedChapterId = chapter.id"
          >
            <span class="flex w-full items-center justify-between gap-2">
              <span class="min-w-0 text-sm font-medium">{{ chapter.heading }}</span>
              <Badge v-if="isChapterAnalyzed(chapter)" class="shrink-0 bg-green-300" variant="outline">已分析</Badge>
            </span>
            <span class="line-clamp-1 text-xs text-muted-foreground">{{ chapter.title }}</span>
          </button>
        </ScrollArea>
      </div>

      <div class="flex min-h-0 flex-col rounded-lg border bg-background">
        <div class="shrink-0 flex items-center justify-between border-b px-4 py-3">
          <div>
            <p class="text-sm font-medium">{{ selectedChapter?.title ?? '章节详情' }}</p>
            <p class="text-xs text-muted-foreground">
              {{ selectedChapter?.id ?? '未选择章节' }}
            </p>
          </div>
          <Badge v-if="selectedChapter" variant="secondary">第 {{ selectedChapter.index }} 章</Badge>
        </div>
        <ScrollArea class="min-h-0 flex-1">
          <div v-if="selectedChapter" class="space-y-4 p-4">
            <p class="whitespace-pre-wrap text-sm leading-7">{{ selectedChapterContent }}</p>

            <div v-if="selectedChapterAnalysis" class="space-y-3 rounded-lg border bg-muted/30 p-4">
              <div>
                <p class="text-sm font-medium">AI 章节分析</p>
                <p class="mt-2 text-sm leading-6 text-muted-foreground">
                  {{ selectedChapterAnalysis.summary }}
                </p>
              </div>

              <div class="grid gap-3 xl:grid-cols-2">
                <div class="rounded-md bg-background p-3">
                  <div class="flex items-center gap-2 text-sm font-medium">
                    <Users class="size-4" />
                    出场角色
                  </div>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <Badge
                      v-for="character in selectedChapterAnalysis.analysis.characters"
                      :key="character.name"
                      variant="outline"
                    >
                      {{ character.name }}
                    </Badge>
                    <span
                      v-if="selectedChapterAnalysis.analysis.characters.length === 0"
                      class="text-xs text-muted-foreground"
                    >
                      未识别角色
                    </span>
                  </div>
                </div>

                <div class="rounded-md bg-background p-3">
                  <div class="flex items-center gap-2 text-sm font-medium">
                    <MessageSquareText class="size-4" />
                    对白素材
                  </div>
                  <p class="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
                    {{ selectedChapterAnalysis.analysis.dialogue_candidates[0] ?? '暂无对白素材' }}
                  </p>
                </div>
              </div>

              <div class="rounded-md bg-background p-3">
                <div class="flex items-center gap-2 text-sm font-medium">
                  <Clapperboard class="size-4" />
                  可改编场景
                </div>
                <div class="mt-3 space-y-2">
                  <div
                    v-for="scene in selectedChapterAnalysis.analysis.scene_candidates"
                    :key="scene.title"
                    class="rounded-md border p-3"
                  >
                    <p class="text-sm font-medium">{{ scene.title }}</p>
                    <p class="mt-1 text-xs leading-5 text-muted-foreground">{{ scene.summary }}</p>
                  </div>
                  <p
                    v-if="selectedChapterAnalysis.analysis.scene_candidates.length === 0"
                    class="text-xs text-muted-foreground"
                  >
                    暂无候选场景。
                  </p>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="p-4 text-sm text-muted-foreground">暂无章节正文。</div>
        </ScrollArea>
      </div>
    </CardContent>
  </Card>

  <AgentFlowDialog
    v-model:open="isAgentFlowOpen"
    :ai-runs="aiRuns"
    :chapter-count="chapters.length"
    :story-elements="storyElements"
    :script-version-name="scriptVersionName"
  />
</template>
