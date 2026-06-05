<script setup lang="ts">
import { computed } from 'vue'
import { BookOpen, Clapperboard, MessageSquareText, Users } from '@lucide/vue'

import type { ChapterAnalysis } from '@/api/projects'
import type { Chapter } from '@/api/chapters'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { normalizeNovelText } from '@/lib/novel-text'

const props = defineProps<{
  chapters: Chapter[]
  chapterAnalyses: ChapterAnalysis[]
  chapterCoverageLabel: string
}>()

const selectedChapterId = defineModel<string | undefined>('selectedChapterId')

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
        <Badge :variant="chapters.length >= 3 ? 'default' : 'secondary'">
          {{ chapterCoverageLabel }}
        </Badge>
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
            还没有保存章节。
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
</template>
