<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileText,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
} from '@lucide/vue'

import { parseChapters, type Chapter } from '@/api/chapters'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
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
const isParsing = ref(false)
const errorMessage = ref('')

const selectedChapter = computed(() => {
  return chapters.value.find((chapter) => chapter.id === selectedChapterId.value) ?? chapters.value[0]
})

const chapterCoverageLabel = computed(() => {
  if (chapters.value.length === 0) return '等待解析'
  return chapters.value.length >= 3 ? '符合 3 章要求' : '章节不足'
})

async function handleParse() {
  errorMessage.value = ''
  isParsing.value = true

  try {
    const result = await parseChapters(novelText.value)
    chapters.value = result.chapters
    selectedChapterId.value = result.chapters[0]?.id
  } catch (error) {
    chapters.value = []
    selectedChapterId.value = undefined
    errorMessage.value = error instanceof Error ? error.message : '章节解析失败'
  } finally {
    isParsing.value = false
  }
}

function clearWorkspace() {
  novelText.value = ''
  chapters.value = []
  selectedChapterId.value = undefined
  errorMessage.value = ''
}
</script>

<template>
  <main class="h-screen overflow-hidden bg-muted/30 text-foreground">
    <section class="mx-auto flex h-full w-full max-w-[1600px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8">
      <header class="shrink-0 flex flex-col gap-3 border-b bg-background/80 pb-4 sm:flex-row sm:items-center sm:justify-between">
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

            <div v-if="errorMessage" class="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
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
              <Badge :variant="chapters.length >= 3 ? 'default' : 'secondary'">{{ chapterCoverageLabel }}</Badge>
            </div>
          </CardHeader>
          <CardContent class="grid min-h-0 flex-1 gap-4 overflow-hidden lg:grid-cols-[260px_minmax(0,1fr)]">
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
                  <span class="line-clamp-1 text-xs text-muted-foreground">{{ chapter.title }}</span>
                </button>
              </ScrollArea>
            </div>

            <div class="flex min-h-0 flex-col rounded-lg border bg-background">
              <div class="shrink-0 flex items-center justify-between border-b px-4 py-3">
                <div>
                  <p class="text-sm font-medium">{{ selectedChapter?.title ?? '章节详情' }}</p>
                  <p class="text-xs text-muted-foreground">{{ selectedChapter?.id ?? '等待选择章节' }}</p>
                </div>
                <Badge v-if="selectedChapter" variant="secondary">第 {{ selectedChapter.index }} 章</Badge>
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
            <CardDescription>当前先完成章节入口，后续继续接入 AI 结构化生成。</CardDescription>
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
                  <p class="mt-2 text-sm text-muted-foreground">识别小说章节并校验是否满足 3 章以上要求。</p>
                </div>
                <div class="rounded-lg border bg-background p-4">
                  <div class="flex items-center gap-2 text-sm font-medium">
                    <span class="size-4 rounded-full border" />
                    角色与事件抽取
                  </div>
                  <p class="mt-2 text-sm text-muted-foreground">后续从章节中抽取角色、地点、剧情事件和关系。</p>
                </div>
                <div class="rounded-lg border bg-background p-4">
                  <div class="flex items-center gap-2 text-sm font-medium">
                    <span class="size-4 rounded-full border" />
                    YAML 剧本生成
                  </div>
                  <p class="mt-2 text-sm text-muted-foreground">将剧情事件改写为场次、动作、对白和旁白。</p>
                </div>
                <Separator />
                <div class="grid grid-cols-3 gap-2 text-center">
                  <div class="rounded-lg border bg-background p-3">
                    <p class="text-lg font-semibold">{{ chapters.length }}</p>
                    <p class="text-xs text-muted-foreground">章节</p>
                  </div>
                  <div class="rounded-lg border bg-background p-3">
                    <p class="text-lg font-semibold">0</p>
                    <p class="text-xs text-muted-foreground">角色</p>
                  </div>
                  <div class="rounded-lg border bg-background p-3">
                    <p class="text-lg font-semibold">0</p>
                    <p class="text-xs text-muted-foreground">场次</p>
                  </div>
                </div>
                  </div>
                </ScrollArea>
              </TabsContent>
              <TabsContent value="yaml" class="mt-4 min-h-0 flex-1">
                <div class="flex h-full min-h-0 flex-col rounded-lg border bg-background p-4">
                  <p class="text-sm font-medium">YAML 剧本预览</p>
                  <pre class="mt-4 min-h-0 flex-1 overflow-auto whitespace-pre-wrap text-xs leading-6 text-muted-foreground">title: {{ title }}
chapters: {{ chapters.length }}
characters: []
scenes: []</pre>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </section>
  </main>
</template>
