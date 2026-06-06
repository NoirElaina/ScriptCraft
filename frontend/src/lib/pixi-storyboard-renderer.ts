import { Application, Container, Graphics, Text } from 'pixi.js'
import { Viewport } from 'pixi-viewport'
import { gsap } from 'gsap'

import type {
  StoryboardActor,
  StoryboardFrame,
  StoryboardScenePlayback,
} from '@/lib/storyboard-timeline'

interface ActorDisplay {
  actor: StoryboardActor
  container: Container
  circle: Graphics
  ring: Graphics
  nameText: Text
  baseX: number
  baseY: number
  currentPosition: string
}

export interface StoryboardRendererEvents {
  onFrameChange?: (index: number) => void
  onComplete?: () => void
}

const WORLD_WIDTH = 1280
const WORLD_HEIGHT = 720
const STAGE_TOP = 120
const STAGE_BOTTOM = 560
const ACTOR_RADIUS = 58

export class PixiStoryboardRenderer {
  private app?: Application
  private viewport?: Viewport
  private scene?: StoryboardScenePlayback
  private frameIndex = 0
  private timeline?: gsap.core.Timeline
  private typingTween?: gsap.core.Tween

  private readonly root = new Container()
  private readonly backgroundLayer = new Container()
  private readonly actorLayer = new Container()
  private readonly overlayLayer = new Container()
  private readonly actorDisplays = new Map<string, ActorDisplay>()

  async mount(host: HTMLElement): Promise<void> {
    const app = new Application()
    await app.init({
      width: host.clientWidth,
      height: host.clientHeight,
      backgroundColor: 0xf8fafc,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      preference: 'webgl',
    })

    app.canvas.className = 'h-full w-full rounded-lg'
    host.appendChild(app.canvas)

    const viewport = new Viewport({
      screenWidth: host.clientWidth,
      screenHeight: host.clientHeight,
      worldWidth: WORLD_WIDTH,
      worldHeight: WORLD_HEIGHT,
      events: app.renderer.events,
    })

    viewport.clamp({ left: 0, right: WORLD_WIDTH, top: 0, bottom: WORLD_HEIGHT, underflow: 'center' })
    viewport.addChild(this.root)
    app.stage.addChild(viewport)

    this.app = app
    this.viewport = viewport
    this.root.addChild(this.backgroundLayer, this.actorLayer, this.overlayLayer)
    this.fit()
  }

  destroy(): void {
    this.stop()
    this.viewport?.destroy({ children: true })
    this.app?.destroy(true, { children: true })
    this.app = undefined
    this.viewport = undefined
    this.actorDisplays.clear()
  }

  resize(width: number, height: number): void {
    if (!this.app || !this.viewport) return
    this.app.renderer.resize(width, height)
    this.viewport.resize(width, height, WORLD_WIDTH, WORLD_HEIGHT)
    this.fit()
  }

  setScene(scene: StoryboardScenePlayback): void {
    this.stop()
    this.scene = scene
    this.frameIndex = 0
    this.backgroundLayer.removeChildren()
    this.actorLayer.removeChildren()
    this.overlayLayer.removeChildren()
    this.actorDisplays.clear()

    this.drawBackground(scene)
    this.drawActors(scene.actors)
    this.fit()
    this.showFrame(0)
  }

  showFrame(index: number): void {
    if (!this.scene || this.scene.frames.length === 0) return
    this.frameIndex = clamp(index, 0, this.scene.frames.length - 1)
    const frame = this.scene.frames[this.frameIndex]
    if (!frame) return
    this.renderFrame(frame)
  }

  playFrom(index: number, speed: number, events: StoryboardRendererEvents = {}): void {
    if (!this.scene || this.scene.frames.length === 0) return
    this.stop()
    this.frameIndex = clamp(index, 0, this.scene.frames.length - 1)

    const timeline = gsap.timeline({
      paused: false,
      onComplete: () => events.onComplete?.(),
    })

    for (let i = this.frameIndex; i < this.scene.frames.length; i += 1) {
      const frame = this.scene.frames[i]
      if (!frame) continue
      timeline.call(() => {
        this.frameIndex = i
        this.renderFrame(frame)
        events.onFrameChange?.(i)
      })
      timeline.to({}, { duration: frame.durationMs / 1000 })
    }

    timeline.timeScale(speed)
    this.timeline = timeline
  }

  pause(): void {
    this.timeline?.pause()
    this.typingTween?.pause()
  }

  resume(): void {
    this.timeline?.resume()
    this.typingTween?.resume()
  }

  stop(): void {
    this.timeline?.kill()
    this.typingTween?.kill()
    this.timeline = undefined
    this.typingTween = undefined
  }

  setSpeed(speed: number): void {
    this.timeline?.timeScale(speed)
    this.typingTween?.timeScale(speed)
  }

  fit(): void {
    if (!this.viewport) return
    gsap.killTweensOf(this.viewport)
    gsap.killTweensOf(this.viewport.scale)
    this.viewport.fitWorld(true)
    this.viewport.moveCenter(WORLD_WIDTH / 2, WORLD_HEIGHT / 2)
  }

  private drawBackground(scene: StoryboardScenePlayback): void {
    const moodColor = moodColorFor(scene.setting.mood || scene.locationName)
    const background = new Graphics()
    background.rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT).fill({ color: 0xf8fafc })
    background.roundRect(52, 42, WORLD_WIDTH - 104, WORLD_HEIGHT - 84, 28).fill({ color: 0xffffff })
    background.roundRect(52, 42, WORLD_WIDTH - 104, WORLD_HEIGHT - 84, 28).stroke({
      color: 0xe2e8f0,
      width: 2,
    })
    background.roundRect(98, STAGE_TOP, WORLD_WIDTH - 196, STAGE_BOTTOM - STAGE_TOP, 22).fill({
      color: moodColor,
      alpha: 0.07,
    })
    background.roundRect(98, STAGE_TOP, WORLD_WIDTH - 196, STAGE_BOTTOM - STAGE_TOP, 22).stroke({
      color: moodColor,
      alpha: 0.18,
      width: 2,
    })

    for (let i = 0; i < 14; i += 1) {
      const x = 148 + i * 74
      background.circle(x, 246, 3).fill({ color: 0x94a3b8, alpha: 0.3 })
      background.circle(x, 408, 3).fill({ color: 0x94a3b8, alpha: 0.22 })
    }

    background.rect(142, STAGE_BOTTOM - 42, WORLD_WIDTH - 284, 3).fill({ color: 0x0f172a, alpha: 0.12 })
    this.backgroundLayer.addChild(background)

    const title = new Text({
      text: scene.title,
      style: {
        fill: 0x0f172a,
        fontFamily: 'Inter, Arial, sans-serif',
        fontSize: 32,
        fontWeight: '700',
      },
    })
    title.position.set(98, 66)

    const subtitle = new Text({
      text: `${scene.locationName || '未标注地点'} · ${scene.timeOfDay || scene.setting.lighting || '未标注时间'}`,
      style: {
        fill: 0x64748b,
        fontFamily: 'Inter, Arial, sans-serif',
        fontSize: 17,
      },
    })
    subtitle.position.set(100, 104)

    this.backgroundLayer.addChild(title, subtitle)
  }

  private drawActors(actors: StoryboardActor[]): void {
    const resolvedPositions = resolveStagePositions(
      actors.map((actor) => ({
        id: actor.id,
        position: actor.position,
      })),
    )

    for (const actor of actors) {
      const position = resolvedPositions.get(actor.id) ?? stagePosition(actor.position)
      const display = createActorDisplay(actor, position.x, position.y)
      display.container.alpha = actor.position.startsWith('offscreen') ? 0 : 1
      this.actorDisplays.set(actor.id, display)
      this.actorLayer.addChild(display.container)
    }
  }

  private renderFrame(frame: StoryboardFrame): void {
    this.typingTween?.kill()
    this.typingTween = undefined
    this.overlayLayer.removeChildren()
    this.applyActions(frame)
    this.highlightSpeaker(frame.speakerId)

    if (frame.type === 'dialogue' && frame.speakerId) {
      this.drawSpeechBubble(frame)
    } else {
      this.drawActionCaption(frame)
    }

    this.drawProgress(frame)
  }

  private applyActions(frame: StoryboardFrame): void {
    const actionByActor = new Map(frame.actions.map((action) => [action.actor, action]))
    const desiredPositions = new Map<string, string>()

    for (const display of this.actorDisplays.values()) {
      desiredPositions.set(display.actor.id, display.currentPosition)
    }

    for (const action of frame.actions) {
      if (!this.actorDisplays.has(action.actor)) continue
      desiredPositions.set(action.actor, action.to || action.from || desiredPositions.get(action.actor) || 'center')
    }

    const resolvedPositions = resolveStagePositions(
      [...desiredPositions.entries()].map(([id, position]) => ({
        id,
        position,
      })),
    )

    for (const display of this.actorDisplays.values()) {
      const action = actionByActor.get(display.actor.id)
      const desiredPosition = desiredPositions.get(display.actor.id) || display.currentPosition
      const targetPosition = resolvedPositions.get(display.actor.id) ?? stagePosition(desiredPosition)

      gsap.killTweensOf(display.container)
      gsap.killTweensOf(display.container.scale)
      gsap.killTweensOf(display.ring)

      if (action?.from && action.motion === 'walk_in') {
        const start = stagePosition(action.from)
        display.container.position.set(start.x, start.y)
        display.container.alpha = 0
      }

      display.currentPosition = desiredPosition
      display.baseX = targetPosition.x
      display.baseY = targetPosition.y

      gsap.to(display.container, {
        x: targetPosition.x,
        y: targetPosition.y,
        alpha: 1,
        duration: action ? motionDuration(action.motion) : 0.28,
        ease: 'power2.out',
      })

      if (action) {
        this.applyActorMotion(display, action.motion)
      }
    }

    if (frame.speakerId && !actionByActor.has(frame.speakerId)) {
      const speaker = this.actorDisplays.get(frame.speakerId)
      if (speaker) {
        gsap.fromTo(
          speaker.container.scale,
          { x: 1.04, y: 1.04 },
          { x: 1, y: 1, duration: 0.32, ease: 'back.out(1.8)' },
        )
      }
    }
  }

  private applyActorMotion(display: ActorDisplay, motion: string): void {
    if (motion === 'step_forward' || motion === 'walk_to' || motion === 'walk_in') {
      gsap.fromTo(display.container.scale, { x: 0.96, y: 0.96 }, { x: 1, y: 1, duration: 0.42 })
      return
    }

    if (motion === 'react' || motion === 'shake') {
      gsap.fromTo(
        display.container.scale,
        { x: 1.12, y: 1.12 },
        { x: 1, y: 1, duration: 0.34, ease: 'back.out(2)' },
      )
      return
    }

    if (motion === 'turn' || motion === 'look_around') {
      gsap.fromTo(display.container, { rotation: -0.04 }, { rotation: 0.04, duration: 0.16, repeat: 1, yoyo: true })
      return
    }

    if (motion === 'point' || motion === 'hand_prop') {
      gsap.fromTo(display.ring.scale, { x: 1, y: 1 }, { x: 1.14, y: 1.14, duration: 0.2, repeat: 1, yoyo: true })
    }
  }

  private highlightSpeaker(speakerId: string): void {
    for (const display of this.actorDisplays.values()) {
      const active = Boolean(speakerId && display.actor.id === speakerId)
      display.ring.visible = active
      display.circle.alpha = active || !speakerId ? 1 : 0.66
      display.nameText.alpha = active || !speakerId ? 1 : 0.72

      if (active) {
        gsap.fromTo(display.ring.scale, { x: 0.96, y: 0.96 }, { x: 1.1, y: 1.1, duration: 0.32, yoyo: true, repeat: 1 })
      }
    }
  }

  private drawSpeechBubble(frame: StoryboardFrame): void {
    const speaker = this.actorDisplays.get(frame.speakerId)
    if (!speaker) return

    const bubbleWidth = 388
    const bubbleHeight = 118
    const bubbleX = clamp(speaker.baseX - bubbleWidth / 2, 102, WORLD_WIDTH - bubbleWidth - 102)
    const bubbleY = clamp(speaker.baseY - ACTOR_RADIUS - bubbleHeight - 28, 144, STAGE_BOTTOM - bubbleHeight - 72)

    const bubble = new Container()
    const shape = new Graphics()
    shape.roundRect(0, 0, bubbleWidth, bubbleHeight, 18).fill({ color: 0xffffff, alpha: 0.97 })
    shape.roundRect(0, 0, bubbleWidth, bubbleHeight, 18).stroke({
      color: speaker.actor.color,
      alpha: 0.55,
      width: 3,
    })

    const speakerName = new Text({
      text: frame.speakerName || speaker.actor.name,
      style: {
        fill: speaker.actor.color,
        fontFamily: 'Inter, Arial, sans-serif',
        fontSize: 17,
        fontWeight: '700',
      },
    })
    speakerName.position.set(18, 14)

    const content = new Text({
      text: '',
      style: {
        fill: 0x0f172a,
        fontFamily: 'Inter, Arial, sans-serif',
        fontSize: 20,
        lineHeight: 30,
        wordWrap: true,
        wordWrapWidth: bubbleWidth - 36,
        breakWords: true,
      },
    })
    content.position.set(18, 46)

    bubble.position.set(bubbleX, bubbleY)
    bubble.alpha = 0
    bubble.scale.set(0.96)
    bubble.addChild(shape, speakerName, content)
    this.overlayLayer.addChild(bubble)

    gsap.to(bubble, { alpha: 1, duration: 0.16, ease: 'power2.out' })
    gsap.to(bubble.scale, { x: 1, y: 1, duration: 0.24, ease: 'back.out(1.6)' })
    this.typeText(content, frame.content, frame.durationMs)
  }

  private drawActionCaption(frame: StoryboardFrame): void {
    if (!frame.content) return

    const targetActorId = frame.actions[0]?.actor || frame.speakerId
    const target = targetActorId ? this.actorDisplays.get(targetActorId) : undefined
    const width = 520
    const x = target ? clamp(target.baseX - width / 2, 130, WORLD_WIDTH - width - 130) : (WORLD_WIDTH - width) / 2
    const y = target ? clamp(target.baseY - ACTOR_RADIUS - 96, 150, STAGE_BOTTOM - 146) : STAGE_BOTTOM - 142

    const card = new Container()
    const shape = new Graphics()
    shape.roundRect(0, 0, width, 82, 16).fill({ color: 0xffffff, alpha: 0.94 })
    shape.roundRect(0, 0, width, 82, 16).stroke({ color: shotColor(frame.type), alpha: 0.36, width: 2 })

    const label = new Text({
      text: frame.label,
      style: {
        fill: shotColor(frame.type),
        fontFamily: 'Inter, Arial, sans-serif',
        fontSize: 15,
        fontWeight: '700',
      },
    })
    label.position.set(18, 12)

    const content = new Text({
      text: '',
      style: {
        fill: 0x0f172a,
        fontFamily: 'Inter, Arial, sans-serif',
        fontSize: 18,
        lineHeight: 26,
        wordWrap: true,
        wordWrapWidth: width - 36,
        breakWords: true,
      },
    })
    content.position.set(18, 40)

    card.position.set(x, y)
    card.alpha = 0
    card.addChild(shape, label, content)
    this.overlayLayer.addChild(card)
    gsap.to(card, { alpha: 1, duration: 0.18 })
    this.typeText(content, frame.content, frame.durationMs)
  }

  private typeText(target: Text, text: string, durationMs: number): void {
    const source = text.trim()
    if (!source) return

    const state = { count: 0 }
    const duration = clamp(source.length * 0.035, 0.28, Math.max(0.28, (durationMs / 1000) * 0.82))
    this.typingTween = gsap.to(state, {
      count: source.length,
      duration,
      ease: 'none',
      onUpdate: () => {
        target.text = source.slice(0, Math.ceil(state.count))
      },
      onComplete: () => {
        target.text = source
      },
    })
  }

  private drawProgress(frame: StoryboardFrame): void {
    if (!this.scene) return
    const width = WORLD_WIDTH - 284
    const progress = this.scene.frames.length === 0 ? 0 : (this.frameIndex + 1) / this.scene.frames.length
    const track = new Graphics()
    track.roundRect(142, 622, width, 8, 999).fill({ color: 0xe2e8f0, alpha: 0.9 })
    track.roundRect(142, 622, width * progress, 8, 999).fill({ color: shotColor(frame.type), alpha: 0.9 })
    this.overlayLayer.addChild(track)
  }
}

function createActorDisplay(actor: StoryboardActor, x: number, y: number): ActorDisplay {
  const container = new Container()
  container.position.set(x, y)

  const ring = new Graphics()
  ring.circle(0, 0, ACTOR_RADIUS + 10).stroke({ color: actor.color, alpha: 0.44, width: 5 })
  ring.visible = false

  const circle = new Graphics()
  circle.circle(0, 0, ACTOR_RADIUS).fill({ color: actor.color, alpha: 0.95 })
  circle.circle(0, 0, ACTOR_RADIUS).stroke({ color: 0xffffff, alpha: 0.9, width: 4 })

  const nameText = new Text({
    text: actor.name,
    style: {
      fill: 0xffffff,
      fontFamily: 'Inter, Arial, sans-serif',
      fontSize: actor.name.length > 4 ? 17 : 19,
      fontWeight: '700',
      align: 'center',
      wordWrap: true,
      wordWrapWidth: ACTOR_RADIUS * 1.55,
      breakWords: true,
    },
  })
  nameText.anchor.set(0.5, 0.5)

  container.addChild(ring, circle, nameText)
  return { actor, container, circle, ring, nameText, baseX: x, baseY: y, currentPosition: actor.position }
}

function stagePosition(position: string): { x: number; y: number } {
  const positions: Record<string, { x: number; y: number }> = {
    offscreen_left: { x: -120, y: STAGE_BOTTOM - 96 },
    left: { x: 298, y: STAGE_BOTTOM - 110 },
    back_left: { x: 420, y: STAGE_BOTTOM - 236 },
    center: { x: WORLD_WIDTH / 2, y: STAGE_BOTTOM - 138 },
    back_right: { x: 860, y: STAGE_BOTTOM - 236 },
    right: { x: 982, y: STAGE_BOTTOM - 110 },
    offscreen_right: { x: WORLD_WIDTH + 120, y: STAGE_BOTTOM - 96 },
  }
  return positions[position] ?? { x: WORLD_WIDTH / 2, y: STAGE_BOTTOM - 138 }
}

function resolveStagePositions(entries: Array<{ id: string; position: string }>): Map<string, { x: number; y: number }> {
  const groups = new Map<string, Array<{ id: string; position: string }>>()
  for (const entry of entries) {
    const group = groups.get(entry.position) ?? []
    group.push(entry)
    groups.set(entry.position, group)
  }

  const resolved = new Map<string, { x: number; y: number }>()
  for (const [position, group] of groups.entries()) {
    const base = stagePosition(position)
    const spacing = position === 'center' ? 160 : 138
    const isOffscreen = position.startsWith('offscreen')

    group.forEach((entry, index) => {
      const offsetIndex = index - (group.length - 1) / 2
      const rowShift = Math.abs(offsetIndex) > 1 ? -92 : 0
      const x = isOffscreen ? base.x : clamp(base.x + offsetIndex * spacing, 176, WORLD_WIDTH - 176)
      const y = isOffscreen ? base.y : clamp(base.y + rowShift + Math.abs(offsetIndex) * 10, STAGE_TOP + 120, STAGE_BOTTOM - 96)
      resolved.set(entry.id, { x, y })
    })
  }
  return resolved
}

function motionDuration(motion: string): number {
  if (motion === 'idle' || motion === 'turn') return 0.24
  if (motion === 'step_forward' || motion === 'react') return 0.34
  return 0.58
}

function moodColorFor(value: string): number {
  if (/雨|cold|冷|蓝|孤独/.test(value)) return 0x2563eb
  if (/紧张|危|红|血|愤怒/.test(value)) return 0xdc2626
  if (/温暖|黄|hope|希望/.test(value)) return 0xca8a04
  if (/神秘|mystery|暗|夜/.test(value)) return 0x7c3aed
  const palette = [0x2563eb, 0x059669, 0x7c3aed, 0xca8a04, 0x0f766e, 0xc2410c]
  let hash = 0
  for (const character of value) {
    hash = (hash * 33 + character.charCodeAt(0)) % palette.length
  }
  return palette[Math.abs(hash) % palette.length] ?? 0x2563eb
}

function shotColor(type: string): number {
  const colors: Record<string, number> = {
    dialogue: 0x059669,
    action: 0x2563eb,
    narration: 0x7c3aed,
    transition: 0xca8a04,
    sound: 0xdc2626,
  }
  return colors[type] ?? 0x475569
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}
