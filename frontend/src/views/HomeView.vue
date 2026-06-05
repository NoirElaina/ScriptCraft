<script setup lang="ts">
import { computed, ref } from 'vue'
import { parse as parseYaml } from 'yaml'
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileText,
  GitBranch,
  Loader2,
  MapPin,
  Play,
  RotateCcw,
  Sparkles,
  Users,
} from '@lucide/vue'

import { parseChapters, type Chapter } from '@/api/chapters'
import { generateScriptYaml } from '@/api/script-yaml'
import { extractStoryElements, type StoryElementsResponse } from '@/api/story-elements'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'

const title = ref('未命名小说')
const novelText = ref('')
const chapters = ref<Chapter[]>([])
const selectedChapterId = ref<string>()
const storyElements = ref<StoryElementsResponse>()
const scriptYaml = ref('')
const isParsing = ref(false)
const isExtracting = ref(false)
const isGeneratingYaml = ref(false)
const errorMessage = ref('')
const storyErrorMessage = ref('')
const yamlErrorMessage = ref('')

type YamlRecord = Record<string, unknown>

interface ScriptCharacter {
  id: string
  name: string
  aliases: string[]
  role: string
  description: string
  motivation: string
}

interface ScriptLocation {
  id: string
  name: string
  description: string
}

interface ScriptEvent {
  id: string
  source_chapter: string
  summary: string
}

interface ScriptBeat {
  type: string
  speaker_id?: string
  content: string
}

interface ScriptScene {
  id: string
  title: string
  source_chapters: string[]
  source_events: string[]
  location_id: string
  time_of_day: string
  characters: string[]
  dramatic_purpose: string
  summary: string
  beats: ScriptBeat[]
}

const selectedChapter = computed(() => {
  return (
    chapters.value.find((chapter) => chapter.id === selectedChapterId.value) ?? chapters.value[0]
  )
})

const chapterCoverageLabel = computed(() => {
  if (chapters.value.length === 0) return '等待解析'
  return chapters.value.length >= 3 ? '符合 3 章要求' : '章节不足'
})

const scriptDocument = computed(() => {
  if (!scriptYaml.value) return undefined

  try {
    const value = parseYaml(scriptYaml.value) as unknown
    return isRecord(value) ? value : undefined
  } catch {
    return undefined
  }
})

const scriptMetadata = computed(() => {
  const metadata = scriptDocument.value?.metadata
  return isRecord(metadata) ? metadata : {}
})

const scriptCharacters = computed<ScriptCharacter[]>(() => {
  return asArray(scriptDocument.value?.characters).map((item, index) => {
    const record = isRecord(item) ? item : {}
    return {
      id: asString(record.id, `char_${String(index + 1).padStart(3, '0')}`),
      name: asString(record.name, '未命名角色'),
      aliases: asStringArray(record.aliases),
      role: asString(record.role, ''),
      description: asString(record.description, ''),
      motivation: asString(record.motivation, ''),
    }
  })
})

const scriptLocations = computed<ScriptLocation[]>(() => {
  return asArray(scriptDocument.value?.locations).map((item, index) => {
    const record = isRecord(item) ? item : {}
    return {
      id: asString(record.id, `loc_${String(index + 1).padStart(3, '0')}`),
      name: asString(record.name, '未命名地点'),
      description: asString(record.description, ''),
    }
  })
})

const scriptEvents = computed<ScriptEvent[]>(() => {
  return asArray(scriptDocument.value?.events).map((item, index) => {
    const record = isRecord(item) ? item : {}
    return {
      id: asString(record.id, `event_${String(index + 1).padStart(3, '0')}`),
      source_chapter: asString(record.source_chapter, ''),
      summary: asString(record.summary, ''),
    }
  })
})

const scriptScenes = computed<ScriptScene[]>(() => {
  return asArray(scriptDocument.value?.scenes).map((item, index) => {
    const record = isRecord(item) ? item : {}
    return {
      id: asString(record.id, `scene_${String(index + 1).padStart(3, '0')}`),
      title: asString(record.title, `场次 ${index + 1}`),
      source_chapters: asStringArray(record.source_chapters),
      source_events: asStringArray(record.source_events),
      location_id: asString(record.location_id, ''),
      time_of_day: asString(record.time_of_day, ''),
      characters: asStringArray(record.characters),
      dramatic_purpose: asString(record.dramatic_purpose, ''),
      summary: asString(record.summary, ''),
      beats: asArray(record.beats).map((beat) => {
        const beatRecord = isRecord(beat) ? beat : {}
        return {
          type: asString(beatRecord.type, 'action'),
          speaker_id: asString(beatRecord.speaker_id, ''),
          content: asString(beatRecord.content, ''),
        }
      }),
    }
  })
})

const scriptParseError = computed(() => scriptYaml.value && !scriptDocument.value)

const characterNameById = computed(() => {
  return new Map(scriptCharacters.value.map((character) => [character.id, character.name]))
})

const locationNameById = computed(() => {
  return new Map(scriptLocations.value.map((location) => [location.id, location.name]))
})

const eventSummaryById = computed(() => {
  return new Map(scriptEvents.value.map((event) => [event.id, event.summary]))
})

async function handleParse() {
  errorMessage.value = ''
  storyErrorMessage.value = ''
  yamlErrorMessage.value = ''
  isParsing.value = true

  try {
    const result = await parseChapters(title.value, novelText.value)
    title.value = result.title
    chapters.value = result.chapters
    storyElements.value = undefined
    scriptYaml.value = ''
    selectedChapterId.value = result.chapters[0]?.id
  } catch (error) {
    chapters.value = []
    storyElements.value = undefined
    scriptYaml.value = ''
    selectedChapterId.value = undefined
    errorMessage.value = error instanceof Error ? error.message : '章节解析失败'
  } finally {
    isParsing.value = false
  }
}

async function handleExtractStoryElements() {
  storyErrorMessage.value = ''
  yamlErrorMessage.value = ''
  isExtracting.value = true

  try {
    storyElements.value = await extractStoryElements(title.value, chapters.value)
    scriptYaml.value = ''
  } catch (error) {
    storyElements.value = undefined
    scriptYaml.value = ''
    storyErrorMessage.value = error instanceof Error ? error.message : '故事元素抽取失败'
  } finally {
    isExtracting.value = false
  }
}

async function handleGenerateScriptYaml() {
  if (!storyElements.value) return

  yamlErrorMessage.value = ''
  isGeneratingYaml.value = true

  try {
    const result = await generateScriptYaml(title.value, chapters.value, storyElements.value)
    scriptYaml.value = result.yaml
  } catch (error) {
    scriptYaml.value = ''
    yamlErrorMessage.value = error instanceof Error ? error.message : '剧本 YAML 生成失败'
  } finally {
    isGeneratingYaml.value = false
  }
}

function clearWorkspace() {
  novelText.value = ''
  chapters.value = []
  storyElements.value = undefined
  scriptYaml.value = ''
  selectedChapterId.value = undefined
  errorMessage.value = ''
  storyErrorMessage.value = ''
  yamlErrorMessage.value = ''
}

function metadataValue(key: string): string {
  return asString(scriptMetadata.value[key], '-')
}

function characterName(id: string): string {
  return characterNameById.value.get(id) ?? id
}

function locationName(id: string): string {
  return locationNameById.value.get(id) ?? id
}

function eventSummary(id: string): string {
  return eventSummaryById.value.get(id) ?? id
}

function beatTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    action: '动作',
    dialogue: '对白',
    narration: '旁白',
    transition: '转场',
    sound: '声音',
  }
  return labels[type] ?? type
}

function beatTypeClass(type: string): string {
  const classes: Record<string, string> = {
    action: 'border-sky-200 bg-sky-50 text-sky-700',
    dialogue: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    narration: 'border-violet-200 bg-violet-50 text-violet-700',
    transition: 'border-amber-200 bg-amber-50 text-amber-700',
    sound: 'border-rose-200 bg-rose-50 text-rose-700',
  }
  return classes[type] ?? 'border-muted bg-muted text-muted-foreground'
}

function isRecord(value: unknown): value is YamlRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function asStringArray(value: unknown): string[] {
  return asArray(value)
    .map((item) => String(item).trim())
    .filter(Boolean)
}

function asString(value: unknown, fallback: string): string {
  if (value === undefined || value === null) return fallback
  const text = String(value).trim()
  return text || fallback
}
</script>

<template>
  <main class="h-screen overflow-hidden bg-muted/30 text-foreground">
    <section
      class="mx-auto flex h-full w-full max-w-[1600px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8"
    >
      <header
        class="shrink-0 flex flex-col gap-3 border-b bg-background/80 pb-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <div class="flex size-9 items-center justify-center rounded-lg border bg-card">
              <Sparkles class="size-4" />
            </div>
            <div>
              <h1 class="text-xl font-semibold tracking-normal">ScriptCraft</h1>
              <p class="text-sm text-muted-foreground">AI 小说转剧本工作台</p>
            </div>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">章节解析</Badge>
          <Badge variant="outline">YAML Schema</Badge>
          <Badge variant="outline">局部重写</Badge>
        </div>
      </header>

      <div class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[420px_minmax(0,1fr)_420px]">
        <Card class="flex min-h-0 flex-col overflow-hidden">
          <CardHeader class="shrink-0">
            <CardTitle class="flex items-center gap-2 text-base">
              <FileText class="size-4" />
              小说输入
            </CardTitle>
            <CardDescription>粘贴 3 个章节以上的小说文本，先完成章节结构识别。</CardDescription>
          </CardHeader>
          <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
            <div class="grid gap-2">
              <Label for="novel-title">作品名</Label>
              <Input id="novel-title" v-model="title" placeholder="输入小说标题" />
            </div>

            <div class="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
              <Label for="novel-text">小说正文</Label>
              <Textarea
                id="novel-text"
                v-model="novelText"
                class="min-h-0 flex-1 resize-none overflow-y-auto leading-7"
                placeholder="第一章 ...&#10;&#10;第二章 ...&#10;&#10;第三章 ..."
              />
            </div>

            <div
              v-if="errorMessage"
              class="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            >
              <AlertTriangle class="mt-0.5 size-4 shrink-0" />
              <span>{{ errorMessage }}</span>
            </div>

            <div class="flex flex-wrap gap-2">
              <Button :disabled="isParsing || !novelText.trim()" @click="handleParse">
                <Loader2 v-if="isParsing" class="size-4 animate-spin" />
                <Play v-else class="size-4" />
                解析章节
              </Button>
              <Button variant="outline" :disabled="isParsing" @click="clearWorkspace">
                <RotateCcw class="size-4" />
                清空
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card class="flex min-h-0 flex-col overflow-hidden">
          <CardHeader class="shrink-0">
            <div class="flex items-start justify-between gap-3">
              <div>
                <CardTitle class="flex items-center gap-2 text-base">
                  <BookOpen class="size-4" />
                  章节解析结果
                </CardTitle>
                <CardDescription>解析后的章节会作为后续角色抽取和剧本生成的输入。</CardDescription>
              </div>
              <Badge :variant="chapters.length >= 3 ? 'default' : 'secondary'">{{
                chapterCoverageLabel
              }}</Badge>
            </div>
          </CardHeader>
          <CardContent
            class="grid min-h-0 flex-1 gap-4 overflow-hidden lg:grid-cols-[260px_minmax(0,1fr)]"
          >
            <div class="flex min-h-0 flex-col rounded-lg border bg-background">
              <div class="shrink-0 flex items-center justify-between border-b px-3 py-2">
                <span class="text-sm font-medium">章节列表</span>
                <Badge variant="outline">{{ chapters.length }} 章</Badge>
              </div>
              <ScrollArea class="min-h-0 flex-1">
                <div v-if="chapters.length === 0" class="p-4 text-sm text-muted-foreground">
                  暂无章节。请先在左侧输入小说正文并点击解析。
                </div>
                <button
                  v-for="chapter in chapters"
                  :key="chapter.id"
                  class="flex w-full flex-col items-start gap-1 border-b px-3 py-3 text-left transition hover:bg-muted/60"
                  :class="chapter.id === selectedChapter?.id ? 'bg-muted' : ''"
                  @click="selectedChapterId = chapter.id"
                >
                  <span class="text-sm font-medium">{{ chapter.heading }}</span>
                  <span class="line-clamp-1 text-xs text-muted-foreground">{{
                    chapter.title
                  }}</span>
                </button>
              </ScrollArea>
            </div>

            <div class="flex min-h-0 flex-col rounded-lg border bg-background">
              <div class="shrink-0 flex items-center justify-between border-b px-4 py-3">
                <div>
                  <p class="text-sm font-medium">{{ selectedChapter?.title ?? '章节详情' }}</p>
                  <p class="text-xs text-muted-foreground">
                    {{ selectedChapter?.id ?? '等待选择章节' }}
                  </p>
                </div>
                <Badge v-if="selectedChapter" variant="secondary"
                  >第 {{ selectedChapter.index }} 章</Badge
                >
              </div>
              <ScrollArea class="min-h-0 flex-1">
                <div v-if="selectedChapter" class="space-y-4 p-4">
                  <p class="whitespace-pre-wrap text-sm leading-7">{{ selectedChapter.content }}</p>
                </div>
                <div v-else class="p-4 text-sm text-muted-foreground">
                  解析完成后，这里会显示选中章节的正文。
                </div>
              </ScrollArea>
            </div>
          </CardContent>
        </Card>

        <Card class="flex min-h-0 flex-col overflow-hidden">
          <CardHeader class="shrink-0">
            <CardTitle class="text-base">剧本生成流程</CardTitle>
            <CardDescription>使用 AI 抽取角色、地点和关键剧情事件。</CardDescription>
          </CardHeader>
          <CardContent class="min-h-0 flex-1 overflow-hidden">
            <Tabs default-value="pipeline" class="flex h-full min-h-0 flex-col">
              <TabsList class="grid w-full shrink-0 grid-cols-2">
                <TabsTrigger value="pipeline">流程</TabsTrigger>
                <TabsTrigger value="yaml">YAML</TabsTrigger>
              </TabsList>
              <TabsContent value="pipeline" class="mt-4 min-h-0 flex-1 overflow-hidden">
                <ScrollArea class="h-full pr-3">
                  <div class="space-y-3">
                    <div class="rounded-lg border bg-background p-4">
                      <div class="flex items-center gap-2 text-sm font-medium">
                        <CheckCircle2 class="size-4 text-emerald-600" />
                        章节解析
                      </div>
                      <p class="mt-2 text-sm text-muted-foreground">
                        识别小说章节并校验是否满足 3 章以上要求。
                      </p>
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
                            调用已配置的大模型，从章节中抽取角色、地点和剧情事件。
                          </p>
                        </div>
                        <Button
                          :disabled="isExtracting || chapters.length < 3"
                          class="shrink-0"
                          @click="handleExtractStoryElements"
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
                            基于章节、角色、地点和事件生成可编辑的剧本 YAML 初稿。
                          </p>
                        </div>
                        <Button
                          :disabled="isGeneratingYaml || !storyElements"
                          class="shrink-0"
                          @click="handleGenerateScriptYaml"
                        >
                          <Loader2 v-if="isGeneratingYaml" class="size-4 animate-spin" />
                          <Sparkles v-else class="size-4" />
                          生成
                        </Button>
                      </div>
                    </div>

                    <div
                      v-if="storyErrorMessage"
                      class="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
                    >
                      <AlertTriangle class="mt-0.5 size-4 shrink-0" />
                      <span>{{ storyErrorMessage }}</span>
                    </div>

                    <div
                      v-if="yamlErrorMessage"
                      class="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
                    >
                      <AlertTriangle class="mt-0.5 size-4 shrink-0" />
                      <span>{{ yamlErrorMessage }}</span>
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
                            <p class="mt-1 text-xs text-muted-foreground">
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
                            <p class="mt-1 text-xs text-muted-foreground">
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
                            <p class="mt-1 text-xs text-muted-foreground">{{ event.summary }}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <Separator />

                    <div class="grid grid-cols-3 gap-2 text-center">
                      <div class="rounded-lg border bg-background p-3">
                        <p class="text-lg font-semibold">{{ chapters.length }}</p>
                        <p class="text-xs text-muted-foreground">章节</p>
                      </div>
                      <div class="rounded-lg border bg-background p-3">
                        <p class="text-lg font-semibold">
                          {{ storyElements?.characters.length ?? 0 }}
                        </p>
                        <p class="text-xs text-muted-foreground">角色</p>
                      </div>
                      <div class="rounded-lg border bg-background p-3">
                        <p class="text-lg font-semibold">{{ storyElements?.events.length ?? 0 }}</p>
                        <p class="text-xs text-muted-foreground">事件</p>
                      </div>
                    </div>
                  </div>
                </ScrollArea>
              </TabsContent>
              <TabsContent value="yaml" class="mt-4 min-h-0 flex-1">
                <div class="flex h-full min-h-0 flex-col rounded-lg border bg-background p-4">
                  <div class="shrink-0 flex items-center justify-between gap-3">
                    <p class="text-sm font-medium">AI 剧本 YAML</p>
                    <Button
                      size="sm"
                      :disabled="isGeneratingYaml || !storyElements"
                      @click="handleGenerateScriptYaml"
                    >
                      <Loader2 v-if="isGeneratingYaml" class="size-4 animate-spin" />
                      <Sparkles v-else class="size-4" />
                      生成
                    </Button>
                  </div>

                  <div
                    v-if="yamlErrorMessage"
                    class="mt-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
                  >
                    <AlertTriangle class="mt-0.5 size-4 shrink-0" />
                    <span>{{ yamlErrorMessage }}</span>
                  </div>

                  <Tabs
                    v-if="scriptYaml"
                    default-value="preview"
                    class="mt-4 flex min-h-0 flex-1 flex-col"
                  >
                    <TabsList class="grid w-full shrink-0 grid-cols-2">
                      <TabsTrigger value="preview">预览</TabsTrigger>
                      <TabsTrigger value="source">源码</TabsTrigger>
                    </TabsList>

                    <TabsContent value="preview" class="mt-4 min-h-0 flex-1 overflow-hidden">
                      <div
                        v-if="scriptParseError"
                        class="flex h-full items-center justify-center rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
                      >
                        YAML 解析失败，请查看源码。
                      </div>

                      <ScrollArea v-else class="h-full pr-3">
                        <div class="space-y-4">
                          <div class="grid grid-cols-3 gap-2 text-center">
                            <div class="rounded-lg border bg-muted/30 p-3">
                              <p class="text-lg font-semibold">{{ scriptCharacters.length }}</p>
                              <p class="text-xs text-muted-foreground">角色</p>
                            </div>
                            <div class="rounded-lg border bg-muted/30 p-3">
                              <p class="text-lg font-semibold">{{ scriptLocations.length }}</p>
                              <p class="text-xs text-muted-foreground">地点</p>
                            </div>
                            <div class="rounded-lg border bg-muted/30 p-3">
                              <p class="text-lg font-semibold">{{ scriptScenes.length }}</p>
                              <p class="text-xs text-muted-foreground">场次</p>
                            </div>
                          </div>

                          <div class="rounded-lg border bg-muted/20 p-3">
                            <div class="flex flex-wrap gap-2">
                              <Badge variant="secondary">{{
                                metadataValue('adaptation_style')
                              }}</Badge>
                              <Badge variant="outline">{{ metadataValue('language') }}</Badge>
                              <Badge variant="outline"
                                >{{ metadataValue('chapters_count') }} 章</Badge
                              >
                            </div>
                            <p class="mt-3 text-xs leading-6 text-muted-foreground">
                              来源：{{ metadataValue('source_title') }}
                            </p>
                          </div>

                          <div class="space-y-2">
                            <div class="flex items-center gap-2 text-sm font-medium">
                              <Users class="size-4" />
                              角色表
                            </div>
                            <div class="space-y-2">
                              <div
                                v-for="character in scriptCharacters"
                                :key="character.id"
                                class="rounded-lg border bg-muted/20 p-3"
                              >
                                <div class="flex items-center justify-between gap-2">
                                  <p class="text-sm font-medium">{{ character.name }}</p>
                                  <Badge variant="outline">{{ character.role || character.id }}</Badge>
                                </div>
                                <p class="mt-2 text-xs leading-5 text-muted-foreground">
                                  {{ character.description || '暂无角色描述' }}
                                </p>
                                <p
                                  v-if="character.motivation"
                                  class="mt-1 text-xs leading-5 text-muted-foreground"
                                >
                                  动机：{{ character.motivation }}
                                </p>
                              </div>
                            </div>
                          </div>

                          <div class="space-y-2">
                            <div class="flex items-center gap-2 text-sm font-medium">
                              <MapPin class="size-4" />
                              地点表
                            </div>
                            <div class="space-y-2">
                              <div
                                v-for="location in scriptLocations"
                                :key="location.id"
                                class="rounded-lg border bg-muted/20 p-3"
                              >
                                <p class="text-sm font-medium">{{ location.name }}</p>
                                <p class="mt-1 text-xs leading-5 text-muted-foreground">
                                  {{ location.description || '暂无地点描述' }}
                                </p>
                              </div>
                            </div>
                          </div>

                          <div class="space-y-3">
                            <div class="flex items-center gap-2 text-sm font-medium">
                              <BookOpen class="size-4" />
                              场次
                            </div>

                            <div
                              v-for="scene in scriptScenes"
                              :key="scene.id"
                              class="rounded-lg border bg-background p-3"
                            >
                              <div class="space-y-2">
                                <div class="flex items-start justify-between gap-3">
                                  <div>
                                    <p class="text-sm font-medium">{{ scene.title }}</p>
                                    <p class="mt-1 text-xs text-muted-foreground">
                                      {{ scene.id }} · {{ locationName(scene.location_id) }}
                                    </p>
                                  </div>
                                  <Badge variant="secondary">{{ scene.time_of_day || '时间未定' }}</Badge>
                                </div>

                                <p class="text-xs leading-5 text-muted-foreground">
                                  {{ scene.summary }}
                                </p>

                                <div class="flex flex-wrap gap-1.5">
                                  <Badge
                                    v-for="characterId in scene.characters"
                                    :key="`${scene.id}-${characterId}`"
                                    variant="outline"
                                  >
                                    {{ characterName(characterId) }}
                                  </Badge>
                                </div>

                                <div
                                  v-if="scene.dramatic_purpose"
                                  class="rounded-md bg-muted/40 p-2 text-xs leading-5 text-muted-foreground"
                                >
                                  叙事作用：{{ scene.dramatic_purpose }}
                                </div>

                                <div v-if="scene.source_events.length" class="space-y-1">
                                  <p class="text-xs font-medium text-muted-foreground">来源事件</p>
                                  <p
                                    v-for="eventId in scene.source_events"
                                    :key="`${scene.id}-${eventId}`"
                                    class="text-xs leading-5 text-muted-foreground"
                                  >
                                    {{ eventSummary(eventId) }}
                                  </p>
                                </div>
                              </div>

                              <div class="mt-3 space-y-2">
                                <div
                                  v-for="(beat, beatIndex) in scene.beats"
                                  :key="`${scene.id}-beat-${beatIndex}`"
                                  class="rounded-md border p-2"
                                >
                                  <div class="mb-1 flex items-center gap-2">
                                    <span
                                      class="rounded border px-1.5 py-0.5 text-[11px]"
                                      :class="beatTypeClass(beat.type)"
                                    >
                                      {{ beatTypeLabel(beat.type) }}
                                    </span>
                                    <span
                                      v-if="beat.speaker_id"
                                      class="text-xs font-medium text-muted-foreground"
                                    >
                                      {{ characterName(beat.speaker_id) }}
                                    </span>
                                  </div>
                                  <p class="whitespace-pre-wrap text-xs leading-5 text-muted-foreground">
                                    {{ beat.content }}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </ScrollArea>
                    </TabsContent>

                    <TabsContent value="source" class="mt-4 min-h-0 flex-1 overflow-hidden">
                      <pre
                        class="h-full overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/20 p-3 text-xs leading-6 text-muted-foreground"
                        >{{ scriptYaml }}</pre
                      >
                    </TabsContent>
                  </Tabs>

                  <div
                    v-else
                    class="mt-4 flex min-h-0 flex-1 items-center justify-center rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
                  >
                    先完成故事元素抽取，再生成剧本 YAML。
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </section>
  </main>
</template>
