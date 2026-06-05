<script setup lang="ts">
import {
  AlertTriangle,
  AlignLeft,
  BookOpen,
  Database,
  FileText,
  Loader2,
  RotateCcw,
} from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { normalizeNovelText } from '@/lib/novel-text'

defineProps<{
  currentProjectTitle: string
  errorMessage: string
  isLoadingWorkspace: boolean
  isParsing: boolean
  isSavingProject: boolean
}>()

const projectTitle = defineModel<string>('projectTitle', { required: true })
const novelText = defineModel<string>('novelText', { required: true })

const emit = defineEmits<{
  parseChapters: []
  saveProject: []
  clearDraft: []
}>()

function handlePaste(event: ClipboardEvent) {
  const pastedText = event.clipboardData?.getData('text')
  if (!pastedText) return

  event.preventDefault()
  const textarea = event.target instanceof HTMLTextAreaElement ? event.target : undefined
  const start = textarea?.selectionStart ?? novelText.value.length
  const end = textarea?.selectionEnd ?? novelText.value.length
  const before = novelText.value.slice(0, start)
  const after = novelText.value.slice(end)
  const inserted = normalizeNovelText(pastedText)

  novelText.value = normalizeNovelText(`${before}${inserted}${after}`)
}

function tidyNovelText() {
  novelText.value = normalizeNovelText(novelText.value)
}
</script>

<template>
  <Card class="flex min-h-0 flex-col overflow-hidden">
    <CardHeader class="shrink-0">
      <CardTitle class="flex items-center gap-2 text-base">
        <FileText class="size-4" />
        小说输入
      </CardTitle>
      <CardDescription>当前项目：{{ currentProjectTitle }}</CardDescription>
    </CardHeader>
    <CardContent class="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
      <div class="grid gap-2">
        <Label for="project-title">作品名</Label>
        <Input id="project-title" v-model="projectTitle" placeholder="输入小说标题" />
      </div>

      <div class="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
        <Label for="project-source-text">小说正文</Label>
        <Textarea
          id="project-source-text"
          v-model="novelText"
          class="min-h-0 flex-1 resize-none overflow-y-auto leading-7"
          placeholder="第1章 ...&#10;&#10;第2章 ...&#10;&#10;第3章 ..."
          @paste="handlePaste"
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
        <Button
          :disabled="isParsing || !novelText.trim() || isLoadingWorkspace"
          @click="emit('parseChapters')"
        >
          <Loader2 v-if="isParsing" class="size-4 animate-spin" />
          <BookOpen v-else class="size-4" />
          解析并保存
        </Button>
        <Button variant="outline" :disabled="isSavingProject" @click="emit('saveProject')">
          <Loader2 v-if="isSavingProject" class="size-4 animate-spin" />
          <Database v-else class="size-4" />
          保存项目
        </Button>
        <Button variant="outline" :disabled="isParsing" @click="tidyNovelText">
          <AlignLeft class="size-4" />
          整理空行
        </Button>
        <Button variant="outline" :disabled="isParsing" @click="emit('clearDraft')">
          <RotateCcw class="size-4" />
          清空输入
        </Button>
      </div>
    </CardContent>
  </Card>
</template>
