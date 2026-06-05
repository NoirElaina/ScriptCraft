<script setup lang="ts">
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

interface ChapterAnalysisLogItem {
  id: string
  status: 'running' | 'succeeded' | 'failed'
  message: string
  createdAt: string
}

const props = defineProps<{
  chaptersLength: number
  chapterAnalysesLength: number
  storyElements?: StoryElementsSnapshot
  scriptYaml: string
  scriptVersionName?: string
  aiRuns: AIRun[]
  chapterAnalysisLogs: ChapterAnalysisLogItem[]
  isLoadingWorkspace: boolean
  isAnalyzingChapters: boolean
  isExtracting: boolean
  isGeneratingYaml: boolean
}>()

const activeFlowTab = defineModel<string>('activeFlowTab', { required: true })
const activeYamlTab = defineModel<string>('activeYamlTab', { required: true })

const emit = defineEmits<{
  refresh: []
  analyzeChapters: []
  extractStoryElements: []
  generateScriptYaml: []
}>()
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
                    :disabled="isAnalyzingChapters || chaptersLength < 3"
                    class="shrink-0"
                    @click="emit('analyzeChapters')"
                  >
                    <Loader2 v-if="isAnalyzingChapters" class="size-4 animate-spin" />
                    <Sparkles v-else class="size-4" />
                    分析
                  </Button>
                </div>
                <div v-if="chapterAnalysisLogs.length > 0" class="mt-3 space-y-2 border-t pt-3">
                  <div
                    v-for="log in chapterAnalysisLogs"
                    :key="log.id"
                    class="flex items-start gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs"
                  >
                    <Loader2
                      v-if="log.status === 'running'"
                      class="mt-0.5 size-3.5 shrink-0 animate-spin text-sky-600"
                    />
                    <CheckCircle2
                      v-else-if="log.status === 'succeeded'"
                      class="mt-0.5 size-3.5 shrink-0 text-emerald-600"
                    />
                    <span v-else class="mt-1.5 size-2 shrink-0 rounded-full bg-destructive" />
                    <span class="min-w-0 flex-1 leading-5">{{ log.message }}</span>
                    <span class="shrink-0 text-muted-foreground">{{ formatTime(log.createdAt) }}</span>
                  </div>
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
                    :disabled="isExtracting || chapterAnalysesLength < chaptersLength || chaptersLength < 3"
                    class="shrink-0"
                    @click="emit('extractStoryElements')"
                  >
                    <Loader2 v-if="isExtracting" class="size-4 animate-spin" />
                    <Sparkles v-else class="size-4" />
                    抽取
                  </Button>
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
                    :disabled="isGeneratingYaml || !storyElements"
                    class="shrink-0"
                    @click="emit('generateScriptYaml')"
                  >
                    <Loader2 v-if="isGeneratingYaml" class="size-4 animate-spin" />
                    <Sparkles v-else class="size-4" />
                    生成
                  </Button>
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
            :has-story-elements="Boolean(storyElements)"
            :is-generating-yaml="isGeneratingYaml"
            @generate="emit('generateScriptYaml')"
          />
        </TabsContent>
      </Tabs>
    </CardContent>
  </Card>
</template>
