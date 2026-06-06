<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  Clapperboard,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Sparkles,
  X,
} from '@lucide/vue'

import type {
  ScriptCharacter,
  ScriptLocation,
  ScriptScene,
  ScriptStoryboardScene,
} from '@/composables/useScriptYamlDocument'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { buildStoryboardScenes } from '@/lib/storyboard-timeline'
import type { StoryboardScenePlayback } from '@/lib/storyboard-timeline'
import StoryboardStage from './StoryboardStage.vue'

const props = defineProps<{
  projectTitle: string
  characters: ScriptCharacter[]
  locations: ScriptLocation[]
  scenes: ScriptScene[]
  storyboardScenes: ScriptStoryboardScene[]
  initialSceneId?: string
}>()

const open = defineModel<boolean>('open', { required: true })

const stageRef = ref<InstanceType<typeof StoryboardStage>>()
const selectedSceneId = ref('')
const currentFrameIndex = ref(0)
const isPlaying = ref(false)
const playbackSpeed = ref(1)

const playbackScenes = computed(() =>
  buildStoryboardScenes({
    characters: props.characters,
    locations: props.locations,
    scenes: props.scenes,
    storyboardScenes: props.storyboardScenes,
  }),
)

const selectedScene = computed<StoryboardScenePlayback | undefined>(() => {
  return playbackScenes.value.find((scene) => scene.id === selectedSceneId.value) ?? playbackScenes.value[0]
})

const currentFrame = computed(() => selectedScene.value?.frames[currentFrameIndex.value])
const canPlay = computed(() => Boolean(selectedScene.value?.frames.length))
const hasStoryboard = computed(() => playbackScenes.value.some((scene) => scene.frames.length > 0))
const progressLabel = computed(() => {
  const scene = selectedScene.value
  if (!scene?.frames.length) return '0 / 0'
  return `${currentFrameIndex.value + 1} / ${scene.frames.length}`
})

watch(
  [open, playbackScenes, () => props.initialSceneId],
  async ([isOpen]) => {
    if (!isOpen || playbackScenes.value.length === 0) return

    const firstScene = playbackScenes.value[0]
    if (!firstScene) return

    const nextSceneId =
      playbackScenes.value.find((scene) => scene.id === props.initialSceneId)?.id ?? firstScene.id

    selectedSceneId.value = nextSceneId
    resetPlayback()
    await nextTick()
    stageRef.value?.showFrame(0)
  },
  { immediate: true },
)

watch(selectedSceneId, async () => {
  resetPlayback()
  await nextTick()
  stageRef.value?.showFrame(0)
})

watch(playbackSpeed, (speed) => {
  stageRef.value?.setSpeed(speed)
})

function togglePlayback() {
  const scene = selectedScene.value
  if (!scene?.frames.length) return

  if (isPlaying.value) {
    stageRef.value?.pause()
    isPlaying.value = false
    return
  }

  if (currentFrameIndex.value >= scene.frames.length - 1) {
    currentFrameIndex.value = 0
    stageRef.value?.showFrame(0)
  }

  isPlaying.value = true
  stageRef.value?.playFrom(currentFrameIndex.value, playbackSpeed.value)
}

function previousFrame() {
  jumpToFrame(Math.max(0, currentFrameIndex.value - 1))
}

function nextFrame() {
  const scene = selectedScene.value
  if (!scene) return
  jumpToFrame(Math.min(scene.frames.length - 1, currentFrameIndex.value + 1))
}

function jumpToFrame(index: number) {
  stageRef.value?.stop()
  isPlaying.value = false
  currentFrameIndex.value = index
  stageRef.value?.showFrame(index)
}

function handleFrameChange(index: number) {
  currentFrameIndex.value = index
}

function handleComplete() {
  isPlaying.value = false
}

function resetPlayback() {
  stageRef.value?.stop()
  currentFrameIndex.value = 0
  isPlaying.value = false
}

function closeDialog() {
  resetPlayback()
  open.value = false
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent
      class="h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-none gap-0 overflow-hidden p-0 sm:max-w-none lg:h-[min(920px,calc(100vh-2rem))] lg:w-[min(1540px,calc(100vw-2rem))]"
      :show-close-button="false"
    >
      <div class="flex h-full min-h-0 flex-col bg-background">
        <div class="shrink-0 border-b px-5 py-4">
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <Clapperboard class="size-5" />
                <DialogTitle class="truncate text-lg font-semibold">剧本预演画布</DialogTitle>
              </div>
              <p class="mt-1 truncate text-sm text-muted-foreground">
                {{ projectTitle }} · {{ selectedScene?.title ?? '未选择场景' }}
              </p>
            </div>

            <div class="flex shrink-0 items-center gap-2">
              <Badge variant="outline">{{ playbackScenes.length }} 场</Badge>
              <Badge variant="secondary">{{ progressLabel }}</Badge>
              <Button size="icon-sm" variant="ghost" @click="closeDialog">
                <X class="size-4" />
              </Button>
            </div>
          </div>
        </div>

        <div class="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_360px] gap-0 lg:grid-cols-[minmax(0,1fr)_360px] lg:grid-rows-none">
          <div class="flex min-h-0 flex-col gap-3 border-b bg-muted/20 p-4 lg:border-r lg:border-b-0">
            <div class="min-h-0 flex-1">
              <StoryboardStage
                v-if="hasStoryboard"
                ref="stageRef"
                :scene="selectedScene"
                @frame-change="handleFrameChange"
                @complete="handleComplete"
              />
              <div
                v-else
                class="flex h-full min-h-[360px] items-center justify-center rounded-lg border border-dashed bg-background text-center text-sm text-muted-foreground lg:min-h-[520px]"
              >
                当前剧本缺少 storyboard 调度，无法预演。
              </div>
            </div>

            <div class="flex shrink-0 flex-wrap items-center justify-between gap-3 rounded-lg border bg-background px-3 py-2">
              <div class="flex items-center gap-2">
                <Button size="icon-sm" variant="outline" :disabled="!canPlay" @click="previousFrame">
                  <SkipBack class="size-4" />
                </Button>
                <Button :disabled="!canPlay" @click="togglePlayback">
                  <Pause v-if="isPlaying" class="size-4" />
                  <Play v-else class="size-4" />
                  {{ isPlaying ? '暂停' : '播放' }}
                </Button>
                <Button size="icon-sm" variant="outline" :disabled="!canPlay" @click="nextFrame">
                  <SkipForward class="size-4" />
                </Button>
              </div>

              <div class="flex items-center gap-1">
                <Button
                  v-for="speed in [0.8, 1, 1.25, 1.5]"
                  :key="speed"
                  size="sm"
                  :variant="playbackSpeed === speed ? 'default' : 'outline'"
                  @click="playbackSpeed = speed"
                >
                  {{ speed }}x
                </Button>
              </div>

              <div class="text-xs text-muted-foreground">固定全景画布</div>
            </div>
          </div>

          <aside class="flex min-h-0 flex-col bg-background">
            <div class="shrink-0 border-b p-4">
              <label class="text-xs font-medium text-muted-foreground">当前场景</label>
              <select
                v-model="selectedSceneId"
                class="mt-2 h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option v-for="scene in playbackScenes" :key="scene.id" :value="scene.id">
                  {{ scene.title }}
                </option>
              </select>

              <div v-if="selectedScene" class="mt-3 rounded-lg border bg-muted/30 p-3">
                <div class="flex flex-wrap gap-1.5">
                <Badge variant="outline">{{ selectedScene.locationName }}</Badge>
                <Badge variant="outline">{{ selectedScene.timeOfDay }}</Badge>
                <Badge variant="outline">{{ selectedScene.setting.mood || '情绪未定' }}</Badge>
                <Badge variant="secondary">{{ selectedScene.actors.length }} 角色</Badge>
                </div>
                <p class="mt-2 text-xs leading-5 text-muted-foreground">
                  {{ selectedScene.summary || selectedScene.dramaticPurpose || '暂无场景概述' }}
                </p>
              </div>
            </div>

            <ScrollArea class="min-h-0 flex-1">
              <div class="space-y-4 p-4">
                <div>
                  <div class="mb-2 flex items-center gap-2 text-sm font-medium">
                    <Sparkles class="size-4" />
                  出场调度
                  </div>
                  <div class="grid gap-2">
                    <div
                      v-for="actor in selectedScene?.actors"
                      :key="actor.id"
                      class="rounded-lg border bg-muted/20 p-3"
                    >
                      <div class="flex items-center justify-between gap-2">
                        <p class="text-sm font-medium">{{ actor.name }}</p>
                        <Badge variant="outline">{{ actor.position }}</Badge>
                      </div>
                      <p class="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                        {{ actor.description || actor.motivation || '暂无角色说明' }}
                      </p>
                    </div>
                  </div>
                </div>

                <Separator />

                <div>
                  <p class="mb-2 text-sm font-medium">导演调度轨道</p>
                  <div class="space-y-2">
                    <button
                      v-for="(frame, index) in selectedScene?.frames"
                      :key="frame.id"
                      class="w-full rounded-lg border p-3 text-left transition hover:bg-muted/50"
                      :class="index === currentFrameIndex ? 'border-foreground bg-muted' : 'bg-background'"
                      @click="jumpToFrame(index)"
                    >
                      <div class="flex items-center justify-between gap-2">
                        <div class="flex items-center gap-2">
                          <span class="rounded border px-1.5 py-0.5 text-[11px]">{{ frame.label }}</span>
                          <span class="text-xs font-medium text-muted-foreground">
                            {{ frame.camera.shot }} · {{ frame.camera.movement }}
                          </span>
                        </div>
                        <span class="text-xs text-muted-foreground">{{ index + 1 }}</span>
                      </div>
                      <p class="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
                        {{ frame.content }}
                      </p>
                      <p v-if="frame.actions.length" class="mt-1 line-clamp-1 text-xs text-muted-foreground">
                        动作：{{ frame.actions.map((action) => `${action.actor}/${action.motion}`).join('，') }}
                      </p>
                    </button>
                  </div>
                </div>
              </div>
            </ScrollArea>

            <div v-if="currentFrame" class="shrink-0 border-t p-4">
              <p class="text-xs font-medium text-muted-foreground">当前台词/动作</p>
              <p class="mt-2 text-sm leading-6">
                {{ currentFrame.speakerName ? `${currentFrame.speakerName}：` : '' }}{{ currentFrame.content }}
              </p>
            </div>
          </aside>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
