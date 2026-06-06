<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { BookOpen, Clapperboard, Download, Loader2, MapPin, Save, Sparkles, Users } from '@lucide/vue'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useScriptYamlDocument } from '@/composables/useScriptYamlDocument'

const StoryboardPlayerDialog = defineAsyncComponent(() => import('./storyboard/StoryboardPlayerDialog.vue'))

const props = defineProps<{
  scriptYaml: string
  projectTitle: string
  scriptVersionName?: string
  hasStoryElements: boolean
  isGeneratingYaml: boolean
  isSavingYaml: boolean
}>()

const activeYamlTab = defineModel<string>('activeYamlTab', { required: true })

const emit = defineEmits<{
  generate: []
  save: [yamlContent: string, versionName: string]
}>()

const editableYaml = ref('')
const versionName = ref('手动编辑版')
const isStoryboardOpen = ref(false)
const initialStoryboardSceneId = ref('')

watch(
  () => props.scriptYaml,
  (value) => {
    editableYaml.value = value
    versionName.value = props.scriptVersionName ? `${props.scriptVersionName} 编辑版` : '手动编辑版'
  },
  { immediate: true },
)

const {
  scriptValidationIssues,
  scriptCharacters,
  scriptLocations,
  scriptScenes,
  scriptStoryboardScenes,
  metadataValue,
  characterName,
  locationName,
  eventSummary,
  beatTypeLabel,
  beatTypeClass,
} = useScriptYamlDocument(editableYaml)

const hasYaml = computed(() => Boolean(editableYaml.value.trim()))
const hasValidationIssue = computed(() => scriptValidationIssues.value.length > 0)
const canSaveYaml = computed(() => hasYaml.value && !hasValidationIssue.value && !props.isSavingYaml)
const canDownloadYaml = computed(() => hasYaml.value && !hasValidationIssue.value)
const canPreviewStoryboard = computed(
  () => hasYaml.value && !hasValidationIssue.value && scriptStoryboardScenes.value.length > 0,
)

function saveYamlVersion() {
  if (!canSaveYaml.value) return
  emit('save', editableYaml.value, versionName.value.trim() || '手动编辑版')
}

function downloadYaml() {
  if (!canDownloadYaml.value) return

  const blob = new Blob([editableYaml.value], { type: 'text/yaml;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${safeFileName(props.projectTitle || 'scriptcraft-script')}.yaml`
  link.click()
  URL.revokeObjectURL(link.href)
}

function openStoryboard(sceneId = '') {
  if (!canPreviewStoryboard.value) return
  initialStoryboardSceneId.value = sceneId || scriptScenes.value[0]?.id || ''
  isStoryboardOpen.value = true
}

function safeFileName(value: string): string {
  const name = value.trim().replace(/[\\/:*?"<>|]+/g, '-')
  return name || 'scriptcraft-script'
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-col rounded-lg border bg-background p-4">
    <div class="shrink-0 flex items-center justify-between gap-3">
      <div>
        <p class="text-sm font-medium">AI 剧本 YAML</p>
        <p class="mt-1 text-xs text-muted-foreground">
          {{ props.scriptVersionName ?? '暂无已保存版本' }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <Button size="sm" variant="outline" :disabled="!canPreviewStoryboard" @click="openStoryboard()">
          <Clapperboard class="size-4" />
          预演
        </Button>
        <Button size="sm" variant="outline" :disabled="!canDownloadYaml" @click="downloadYaml">
          <Download class="size-4" />
          导出
        </Button>
        <Button size="sm" :disabled="isGeneratingYaml || !hasStoryElements" @click="emit('generate')">
          <Loader2 v-if="isGeneratingYaml" class="size-4 animate-spin" />
          <Sparkles v-else class="size-4" />
          生成
        </Button>
      </div>
    </div>

    <Tabs v-if="hasYaml" v-model="activeYamlTab" class="mt-4 flex min-h-0 flex-1 flex-col">
      <TabsList class="grid w-full shrink-0 grid-cols-2">
        <TabsTrigger value="preview">预览</TabsTrigger>
        <TabsTrigger value="source">编辑</TabsTrigger>
      </TabsList>

      <TabsContent value="preview" class="mt-4 min-h-0 flex-1 overflow-hidden">
        <div
          v-if="hasValidationIssue"
          class="flex h-full items-center justify-center rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
        >
          {{ scriptValidationIssues[0] }}，请切换到编辑模式修正。
        </div>

        <ScrollArea v-else class="h-full pr-3">
          <div class="space-y-4">
            <div class="grid grid-cols-4 gap-2 text-center">
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
              <div class="rounded-lg border bg-muted/30 p-3">
                <p class="text-lg font-semibold">{{ scriptStoryboardScenes.length }}</p>
                <p class="text-xs text-muted-foreground">分镜</p>
              </div>
            </div>

            <div class="rounded-lg border bg-muted/20 p-3">
              <div class="flex flex-wrap gap-2">
                <Badge variant="secondary">{{ metadataValue('adaptation_style') }}</Badge>
                <Badge variant="outline">{{ metadataValue('language') }}</Badge>
                <Badge variant="outline">{{ metadataValue('chapters_count') }} 章</Badge>
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
                  <p v-if="character.motivation" class="mt-1 text-xs leading-5 text-muted-foreground">
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

              <div v-for="scene in scriptScenes" :key="scene.id" class="rounded-lg border bg-background p-3">
                <div class="space-y-2">
                  <div class="flex items-start justify-between gap-3">
                    <div>
                      <p class="text-sm font-medium">{{ scene.title }}</p>
                      <p class="mt-1 text-xs text-muted-foreground">
                        {{ scene.id }} · {{ locationName(scene.location_id) }}
                      </p>
                    </div>
                    <div class="flex shrink-0 items-center gap-2">
                      <Badge variant="secondary">{{ scene.time_of_day || '时间未定' }}</Badge>
                      <Button size="sm" variant="outline" @click="openStoryboard(scene.id)">
                        <Clapperboard class="size-4" />
                        预演
                      </Button>
                    </div>
                  </div>

                  <p class="text-xs leading-5 text-muted-foreground">{{ scene.summary }}</p>

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
                      <span class="rounded border px-1.5 py-0.5 text-[11px]" :class="beatTypeClass(beat.type)">
                        {{ beatTypeLabel(beat.type) }}
                      </span>
                      <span v-if="beat.speaker_id" class="text-xs font-medium text-muted-foreground">
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
        <div class="flex h-full min-h-0 flex-col gap-3">
          <div class="grid shrink-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
            <Input v-model="versionName" placeholder="版本名称" />
            <Button :disabled="!canSaveYaml" @click="saveYamlVersion">
              <Loader2 v-if="isSavingYaml" class="size-4 animate-spin" />
              <Save v-else class="size-4" />
              保存版本
            </Button>
          </div>

          <div
            v-if="hasValidationIssue"
            class="shrink-0 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            <p class="font-medium">YAML 解析或结构校验失败，修正后再保存。</p>
            <p class="mt-1 text-xs leading-5">{{ scriptValidationIssues[0] }}</p>
          </div>

          <Textarea
            v-model="editableYaml"
            class="min-h-0 flex-1 resize-none overflow-auto font-mono text-xs leading-6"
            spellcheck="false"
          />
        </div>
      </TabsContent>
    </Tabs>

    <div
      v-else
      class="mt-4 flex min-h-0 flex-1 items-center justify-center rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
    >
      当前项目还没有剧本 YAML。
    </div>

    <StoryboardPlayerDialog
      v-if="isStoryboardOpen"
      v-model:open="isStoryboardOpen"
      :project-title="projectTitle"
      :characters="scriptCharacters"
      :locations="scriptLocations"
      :scenes="scriptScenes"
      :storyboard-scenes="scriptStoryboardScenes"
      :initial-scene-id="initialStoryboardSceneId"
    />
  </div>
</template>
