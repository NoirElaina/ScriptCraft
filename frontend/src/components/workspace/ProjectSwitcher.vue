<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  AlertTriangle,
  ChevronDown,
  FolderOpen,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from '@lucide/vue'

import type { ProjectListItem } from '@/api/projects'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { formatTime, statusLabel } from '@/lib/workspace-formatters'

const props = defineProps<{
  projects: ProjectListItem[]
  currentProjectId?: number
  currentProjectTitle?: string
  isLoadingProjects: boolean
  isCreatingProject: boolean
  isDeletingProject: boolean
  errorMessage: string
}>()

const newProjectTitle = defineModel<string>('newProjectTitle', { required: true })
const isOpen = ref(false)

const currentProjectLabel = computed(() => props.currentProjectTitle || '选择项目')

const emit = defineEmits<{
  refresh: []
  create: []
  open: [projectId: number]
  deleteProject: [project: ProjectListItem]
}>()

function openProject(projectId: number) {
  emit('open', projectId)
  isOpen.value = false
}
</script>

<template>
  <div class="relative">
    <div class="flex items-center gap-2">
      <Button variant="outline" class="h-9 min-w-[220px] justify-between" @click="isOpen = !isOpen">
        <span class="flex min-w-0 items-center gap-2">
          <FolderOpen class="size-4 shrink-0" />
          <span class="truncate">{{ currentProjectLabel }}</span>
        </span>
        <ChevronDown class="size-4 shrink-0 text-muted-foreground" />
      </Button>

      <Button size="icon" variant="outline" :disabled="isLoadingProjects" @click="emit('refresh')">
        <Loader2 v-if="isLoadingProjects" class="size-4 animate-spin" />
        <RefreshCw v-else class="size-4" />
      </Button>
    </div>

    <div
      v-if="isOpen"
      class="absolute right-0 z-20 mt-2 w-[380px] rounded-lg border bg-background p-3 shadow-lg"
    >
      <div class="flex gap-2">
        <Input
          v-model="newProjectTitle"
          placeholder="新项目标题"
          @keydown.enter="emit('create')"
        />
        <Button :disabled="isCreatingProject" @click="emit('create')">
          <Loader2 v-if="isCreatingProject" class="size-4 animate-spin" />
          <Plus v-else class="size-4" />
          新建
        </Button>
      </div>

      <div
        v-if="errorMessage"
        class="mt-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
      >
        <AlertTriangle class="mt-0.5 size-4 shrink-0" />
        <span>{{ errorMessage }}</span>
      </div>

      <ScrollArea class="mt-3 h-[320px]">
        <div v-if="projects.length === 0" class="p-4 text-sm text-muted-foreground">
          暂无项目。
        </div>
        <div v-else class="space-y-2 pr-3">
          <div
            v-for="project in projects"
            :key="project.id"
            class="rounded-lg border bg-background transition hover:bg-muted/50"
            :class="project.id === currentProjectId ? 'border-primary bg-muted/60' : ''"
          >
            <button class="w-full text-left" @click="openProject(project.id)">
              <div class="space-y-2 p-3">
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0">
                    <p class="truncate text-sm font-medium">{{ project.title }}</p>
                    <p class="mt-1 text-xs text-muted-foreground">
                      {{ formatTime(project.updated_at) }}
                    </p>
                  </div>
                  <Badge variant="outline" class="shrink-0">
                    {{ statusLabel(project.status) }}
                  </Badge>
                </div>
                <div class="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                  <span>{{ project.chapter_count }} 章</span>
                  <span>{{ project.script_version_count }} 版剧本</span>
                </div>
              </div>
            </button>
            <div class="border-t px-3 py-2">
              <Button
                size="sm"
                variant="outline"
                class="h-7 w-full text-xs"
                :disabled="isDeletingProject"
                @click="emit('deleteProject', project)"
              >
                <Trash2 class="size-3.5" />
                删除
              </Button>
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  </div>
</template>
