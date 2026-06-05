<script setup lang="ts">
import { toRef } from 'vue'
import { BookOpen, Loader2, MapPin, Sparkles, Users } from '@lucide/vue'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useScriptYamlDocument } from '@/composables/useScriptYamlDocument'

const props = defineProps<{
  scriptYaml: string
  hasStoryElements: boolean
  isGeneratingYaml: boolean
}>()

const activeYamlTab = defineModel<string>('activeYamlTab', { required: true })

const emit = defineEmits<{
  generate: []
}>()

const {
  scriptParseError,
  scriptCharacters,
  scriptLocations,
  scriptScenes,
  metadataValue,
  characterName,
  locationName,
  eventSummary,
  beatTypeLabel,
  beatTypeClass,
} = useScriptYamlDocument(toRef(props, 'scriptYaml'))
</script>

<template>
  <div class="flex h-full min-h-0 flex-col rounded-lg border bg-background p-4">
    <div class="shrink-0 flex items-center justify-between gap-3">
      <p class="text-sm font-medium">AI 剧本 YAML</p>
      <Button size="sm" :disabled="isGeneratingYaml || !hasStoryElements" @click="emit('generate')">
        <Loader2 v-if="isGeneratingYaml" class="size-4 animate-spin" />
        <Sparkles v-else class="size-4" />
        生成
      </Button>
    </div>

    <Tabs v-if="scriptYaml" v-model="activeYamlTab" class="mt-4 flex min-h-0 flex-1 flex-col">
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
                    <Badge variant="secondary">{{ scene.time_of_day || '时间未定' }}</Badge>
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
      当前项目还没有剧本 YAML。
    </div>
  </div>
</template>
