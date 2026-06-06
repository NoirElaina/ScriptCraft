<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { PixiStoryboardRenderer } from '@/lib/pixi-storyboard-renderer'
import type { StoryboardScenePlayback } from '@/lib/storyboard-timeline'

const props = defineProps<{
  scene?: StoryboardScenePlayback
}>()

const emit = defineEmits<{
  frameChange: [index: number]
  complete: []
}>()

const hostRef = ref<HTMLElement>()
const renderer = shallowRef<PixiStoryboardRenderer>()
let resizeObserver: ResizeObserver | undefined

watch(
  () => props.scene,
  async (scene) => {
    if (!scene) return
    await ensureRenderer()
    renderer.value?.setScene(scene)
    emit('frameChange', 0)
  },
  { immediate: true },
)

onMounted(async () => {
  await ensureRenderer()
  if (props.scene) {
    renderer.value?.setScene(props.scene)
    emit('frameChange', 0)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  renderer.value?.destroy()
})

async function ensureRenderer(): Promise<void> {
  if (renderer.value || !hostRef.value) return
  await nextTick()
  if (!hostRef.value) return

  const nextRenderer = new PixiStoryboardRenderer()
  await nextRenderer.mount(hostRef.value)
  renderer.value = nextRenderer

  resizeObserver = new ResizeObserver(([entry]) => {
    if (!entry) return
    const width = Math.floor(entry.contentRect.width)
    const height = Math.floor(entry.contentRect.height)
    if (width > 0 && height > 0) {
      nextRenderer.resize(width, height)
    }
  })
  resizeObserver.observe(hostRef.value)
}

function showFrame(index: number) {
  renderer.value?.stop()
  renderer.value?.showFrame(index)
  emit('frameChange', index)
}

function playFrom(index: number, speed: number) {
  renderer.value?.playFrom(index, speed, {
    onFrameChange: (frameIndex) => emit('frameChange', frameIndex),
    onComplete: () => emit('complete'),
  })
}

function pause() {
  renderer.value?.pause()
}

function resume() {
  renderer.value?.resume()
}

function stop() {
  renderer.value?.stop()
}

function setSpeed(speed: number) {
  renderer.value?.setSpeed(speed)
}

function fit() {
  renderer.value?.fit()
}

defineExpose({
  showFrame,
  playFrom,
  pause,
  resume,
  stop,
  setSpeed,
  fit,
})
</script>

<template>
  <div ref="hostRef" class="h-full min-h-[360px] w-full overflow-hidden rounded-lg border bg-muted/40 lg:min-h-[520px]" />
</template>
