import { computed, type Ref } from 'vue'
import { parse as parseYaml } from 'yaml'

type YamlRecord = Record<string, unknown>

export interface ScriptCharacter {
  id: string
  name: string
  aliases: string[]
  role: string
  description: string
  motivation: string
}

export interface ScriptLocation {
  id: string
  name: string
  description: string
}

export interface ScriptEvent {
  id: string
  source_chapter: string
  summary: string
}

export interface ScriptBeat {
  id: string
  type: string
  speaker_id?: string
  content: string
}

export interface ScriptScene {
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

export interface ScriptStoryboardSetting {
  mood: string
  weather: string
  lighting: string
  background: string
}

export interface ScriptStoryboardCastMember {
  character_id: string
  position: string
  pose: string
}

export interface ScriptStoryboardCamera {
  shot: string
  target: string
  movement: string
}

export interface ScriptStoryboardAction {
  actor: string
  motion: string
  from: string
  to: string
  emotion: string
}

export interface ScriptStoryboardDialogue {
  speaker_id: string
  text: string
}

export interface ScriptStoryboardProp {
  id: string
  name: string
  action: string
  from: string
  to: string
}

export interface ScriptStoryboardShot {
  id: string
  source_beat_id: string
  type: string
  duration_ms: number
  camera: ScriptStoryboardCamera
  actions: ScriptStoryboardAction[]
  dialogue?: ScriptStoryboardDialogue
  effects: string[]
  props: ScriptStoryboardProp[]
}

export interface ScriptStoryboardScene {
  scene_id: string
  setting: ScriptStoryboardSetting
  cast: ScriptStoryboardCastMember[]
  timeline: ScriptStoryboardShot[]
}

export function useScriptYamlDocument(scriptYaml: Ref<string>) {
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
    return asArray(scriptDocument.value?.characters).map((item) => {
      const record = isRecord(item) ? item : {}
      return {
        id: asString(record.id, ''),
        name: asString(record.name, ''),
        aliases: asStringArray(record.aliases),
        role: asString(record.role, ''),
        description: asString(record.description, ''),
        motivation: asString(record.motivation, ''),
      }
    })
  })

  const scriptLocations = computed<ScriptLocation[]>(() => {
    return asArray(scriptDocument.value?.locations).map((item) => {
      const record = isRecord(item) ? item : {}
      return {
        id: asString(record.id, ''),
        name: asString(record.name, ''),
        description: asString(record.description, ''),
      }
    })
  })

  const scriptEvents = computed<ScriptEvent[]>(() => {
    return asArray(scriptDocument.value?.events).map((item) => {
      const record = isRecord(item) ? item : {}
      return {
        id: asString(record.id, ''),
        source_chapter: asString(record.source_chapter, ''),
        summary: asString(record.summary, ''),
      }
    })
  })

  const scriptScenes = computed<ScriptScene[]>(() => {
    return asArray(scriptDocument.value?.scenes).map((item) => {
      const record = isRecord(item) ? item : {}
      return {
        id: asString(record.id, ''),
        title: asString(record.title, ''),
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
            id: asString(beatRecord.id, ''),
            type: asString(beatRecord.type, ''),
            speaker_id: asString(beatRecord.speaker_id, ''),
            content: asString(beatRecord.content, ''),
          }
        }),
      }
    })
  })

  const scriptStoryboardScenes = computed<ScriptStoryboardScene[]>(() => {
    const storyboard = scriptDocument.value?.storyboard
    const storyboardRecord = isRecord(storyboard) ? storyboard : {}

    return asArray(storyboardRecord.scenes).map((item) => {
      const record = isRecord(item) ? item : {}
      const setting = isRecord(record.setting) ? record.setting : {}
      return {
        scene_id: asString(record.scene_id, ''),
        setting: {
          mood: asString(setting.mood, ''),
          weather: asString(setting.weather, ''),
          lighting: asString(setting.lighting, ''),
          background: asString(setting.background, ''),
        },
        cast: asArray(record.cast).map((member) => {
          const memberRecord = isRecord(member) ? member : {}
          return {
            character_id: asString(memberRecord.character_id, ''),
            position: asString(memberRecord.position, ''),
            pose: asString(memberRecord.pose, ''),
          }
        }),
        timeline: asArray(record.timeline).map((shot) => parseStoryboardShot(shot)),
      }
    })
  })

  const scriptParseError = computed(() => Boolean(scriptYaml.value && !scriptDocument.value))

  const scriptValidationIssues = computed(() => {
    if (!scriptYaml.value.trim()) return []
    if (!scriptDocument.value) return ['YAML 解析失败']

    const issues: string[] = []
    const requiredKeys = ['schema_version', 'title', 'metadata', 'characters', 'locations', 'events', 'scenes', 'storyboard']
    for (const key of requiredKeys) {
      if (!(key in scriptDocument.value)) {
        issues.push(`缺少顶层字段：${key}`)
      }
    }
    if (asString(scriptDocument.value.schema_version, '') !== '2.0') {
      issues.push('schema_version 必须是 2.0')
    }

    const characterIds = new Set(scriptCharacters.value.map((character) => character.id).filter(Boolean))
    const locationIds = new Set(scriptLocations.value.map((location) => location.id).filter(Boolean))
    const eventIds = new Set(scriptEvents.value.map((event) => event.id).filter(Boolean))
    const characterLabels = new Map(scriptCharacters.value.map((character) => [character.id, characterLabel(character)]))
    const locationLabels = new Map(scriptLocations.value.map((location) => [location.id, namedEntityLabel(location.id, location.name)]))
    const eventLabels = new Map(scriptEvents.value.map((event) => [event.id, eventLabel(event)]))
    const narratorCharacterIds = new Set(
      scriptCharacters.value.filter((character) => isNarratorCharacter(character)).map((character) => character.id),
    )
    if (narratorCharacterIds.size > 0) {
      issues.push(`characters 包含旁白类角色：${entityLabels(narratorCharacterIds, characterLabels)}；旁白必须使用 narration 类型，不进入 characters`)
    }
    const sceneIds = new Set<string>()
    const beatIdsByScene = new Map<string, Set<string>>()

    if (!scriptScenes.value.length) {
      issues.push('至少需要包含一个 scene')
    }

    for (const scene of scriptScenes.value) {
      if (!scene.id) {
        issues.push('scene 缺少 id')
        continue
      }
      if (sceneIds.has(scene.id)) {
        issues.push(`scene.id 重复：${scene.id}`)
      }
      sceneIds.add(scene.id)
      if (!locationIds.has(scene.location_id)) {
        issues.push(`${scene.id} 引用了不存在的 location_id：${entityLabel(scene.location_id, locationLabels)}`)
      }
      for (const characterId of scene.characters) {
        if (!characterIds.has(characterId)) {
          issues.push(`${scene.id} 引用了不存在的角色：${entityLabel(characterId, characterLabels)}`)
        } else if (narratorCharacterIds.has(characterId)) {
          issues.push(`${scene.id} 把旁白作为角色引用：${entityLabel(characterId, characterLabels)}；旁白必须使用 narration 类型，不进入 scene.characters`)
        }
      }
      for (const eventId of scene.source_events) {
        if (!eventIds.has(eventId)) {
          issues.push(`${scene.id} 引用了不存在的事件：${entityLabel(eventId, eventLabels)}`)
        }
      }
      if (!scene.beats.length) {
        issues.push(`${scene.id} 至少需要包含一个 beat`)
      }
      const beatIds = new Set<string>()
      for (const beat of scene.beats) {
        if (!beat.id) {
          issues.push(`${scene.id} 存在缺少 id 的 beat`)
        } else if (beatIds.has(beat.id)) {
          issues.push(`${scene.id} 的 beat.id 重复：${beat.id}`)
        }
        if (beat.id) beatIds.add(beat.id)
        if (!beat.type || !beat.content) {
          issues.push(`${scene.id} 的 ${beat.id || 'beat'} 缺少 type 或 content`)
        }
        if (beat.type === 'dialogue' && !beat.speaker_id) {
          issues.push(`${scene.id} 的 dialogue beat 缺少 speaker_id`)
        }
        if (beat.speaker_id && !characterIds.has(beat.speaker_id)) {
          issues.push(`${scene.id} 的 ${beat.id || 'beat'} 引用了不存在的 speaker_id：${entityLabel(beat.speaker_id, characterLabels)}`)
        } else if (beat.speaker_id && narratorCharacterIds.has(beat.speaker_id)) {
          issues.push(`${scene.id} 的 ${beat.id || 'beat'} 把旁白作为 speaker_id：${entityLabel(beat.speaker_id, characterLabels)}；旁白必须使用 narration 类型`)
        }
      }
      beatIdsByScene.set(scene.id, beatIds)
    }

    const storyboardSceneIds = new Set<string>()
    if (!scriptStoryboardScenes.value.length) {
      issues.push('storyboard.scenes 必须包含分镜调度')
    }
    for (const storyboardScene of scriptStoryboardScenes.value) {
      if (!storyboardScene.scene_id) {
        issues.push('storyboard scene 缺少 scene_id')
        continue
      }
      if (!sceneIds.has(storyboardScene.scene_id)) {
        issues.push(`storyboard 引用了不存在的 scene_id：${storyboardScene.scene_id}`)
      }
      if (storyboardSceneIds.has(storyboardScene.scene_id)) {
        issues.push(`storyboard.scene_id 重复：${storyboardScene.scene_id}`)
      }
      storyboardSceneIds.add(storyboardScene.scene_id)

      const castIds = new Set<string>()
      for (const member of storyboardScene.cast) {
        if (!characterIds.has(member.character_id)) {
          issues.push(`${storyboardScene.scene_id} 的 cast 引用了不存在的角色：${entityLabel(member.character_id, characterLabels)}`)
        } else if (narratorCharacterIds.has(member.character_id)) {
          issues.push(`${storyboardScene.scene_id} 的 cast 包含旁白角色：${entityLabel(member.character_id, characterLabels)}；旁白不进入 storyboard.cast`)
        }
        if (member.position.startsWith('offscreen')) {
          issues.push(`${storyboardScene.scene_id} 的 cast.position 不能使用场外位置：${member.position}`)
        }
        if (member.character_id) {
          castIds.add(member.character_id)
        }
      }

      if (!storyboardScene.timeline.length) {
        issues.push(`${storyboardScene.scene_id} 缺少 storyboard.timeline`)
      }

      const beatIds = beatIdsByScene.get(storyboardScene.scene_id) ?? new Set<string>()
      for (const shot of storyboardScene.timeline) {
        if (!shot.id || !shot.source_beat_id || !shot.type) {
          issues.push(`${storyboardScene.scene_id} 存在字段不完整的 shot`)
        }
        if (shot.source_beat_id && !beatIds.has(shot.source_beat_id)) {
          issues.push(`${shot.id || storyboardScene.scene_id} 引用了不存在的 source_beat_id：${shot.source_beat_id}`)
        }
        if (shot.duration_ms <= 0) {
          issues.push(`${shot.id || storyboardScene.scene_id} 的 duration_ms 必须大于 0`)
        }
        if (!shot.camera.shot || !shot.camera.target || !shot.camera.movement) {
          issues.push(`${shot.id || storyboardScene.scene_id} 缺少 camera 调度`)
        }
        if (shot.type === 'action' && shot.actions.length === 0 && shot.effects.length === 0 && shot.props.length === 0) {
          issues.push(`${shot.id || storyboardScene.scene_id} 是 action 类型，必须包含 actions、effects 或 props`)
        }
        for (const action of shot.actions) {
          if (!characterIds.has(action.actor)) {
            issues.push(`${shot.id || storyboardScene.scene_id} 的 action 引用了不存在的角色：${entityLabel(action.actor, characterLabels)}`)
          } else if (narratorCharacterIds.has(action.actor)) {
            issues.push(`${shot.id || storyboardScene.scene_id} 的 action 把旁白作为 actor：${entityLabel(action.actor, characterLabels)}；旁白必须使用 narration 类型`)
          } else if (!castIds.has(action.actor)) {
            issues.push(`${shot.id || storyboardScene.scene_id} 的 action 角色未出现在 cast 中：${entityLabel(action.actor, characterLabels)}；当前 cast：${entityLabels(castIds, characterLabels)}`)
          }
        }
        if (shot.type === 'dialogue') {
          if (!shot.dialogue?.speaker_id || !shot.dialogue.text) {
            issues.push(`${shot.id || storyboardScene.scene_id} 是 dialogue 类型，必须包含 dialogue.speaker_id 和 dialogue.text`)
          } else if (!characterIds.has(shot.dialogue.speaker_id)) {
            issues.push(`${shot.id || storyboardScene.scene_id} 的 dialogue 引用了不存在的角色：${entityLabel(shot.dialogue.speaker_id, characterLabels)}`)
          } else if (narratorCharacterIds.has(shot.dialogue.speaker_id)) {
            issues.push(`${shot.id || storyboardScene.scene_id} 的 dialogue 把旁白作为 speaker_id：${entityLabel(shot.dialogue.speaker_id, characterLabels)}；旁白必须使用 narration 类型，不进入主场景`)
          } else if (!castIds.has(shot.dialogue.speaker_id)) {
            issues.push(`${shot.id || storyboardScene.scene_id} 的 dialogue 角色未出现在 cast 中：${entityLabel(shot.dialogue.speaker_id, characterLabels)}；当前 cast：${entityLabels(castIds, characterLabels)}`)
          }
        }
      }
    }

    for (const sceneId of sceneIds) {
      if (!storyboardSceneIds.has(sceneId)) {
        issues.push(`storyboard 缺少场景调度：${sceneId}`)
      }
    }

    return issues
  })

  const characterNameById = computed(() => {
    return new Map(scriptCharacters.value.map((character) => [character.id, character.name || character.id]))
  })

  const locationNameById = computed(() => {
    return new Map(scriptLocations.value.map((location) => [location.id, location.name || location.id]))
  })

  const eventSummaryById = computed(() => {
    return new Map(scriptEvents.value.map((event) => [event.id, event.summary || event.id]))
  })

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

  return {
    scriptParseError,
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
  }
}

function parseStoryboardShot(value: unknown): ScriptStoryboardShot {
  const record = isRecord(value) ? value : {}
  const camera = isRecord(record.camera) ? record.camera : {}
  const dialogue = isRecord(record.dialogue) ? record.dialogue : undefined

  return {
    id: asString(record.id, ''),
    source_beat_id: asString(record.source_beat_id, ''),
    type: asString(record.type, ''),
    duration_ms: asNumber(record.duration_ms),
    camera: {
      shot: asString(camera.shot, ''),
      target: asString(camera.target, ''),
      movement: asString(camera.movement, ''),
    },
    actions: asArray(record.actions).map((action) => {
      const actionRecord = isRecord(action) ? action : {}
      return {
        actor: asString(actionRecord.actor, ''),
        motion: asString(actionRecord.motion, ''),
        from: asString(actionRecord.from, ''),
        to: asString(actionRecord.to, ''),
        emotion: asString(actionRecord.emotion, ''),
      }
    }),
    dialogue: dialogue
      ? {
          speaker_id: asString(dialogue.speaker_id, ''),
          text: asString(dialogue.text, ''),
        }
      : undefined,
    effects: asStringArray(record.effects),
    props: asArray(record.props).map((prop) => {
      const propRecord = isRecord(prop) ? prop : {}
      return {
        id: asString(propRecord.id, ''),
        name: asString(propRecord.name, ''),
        action: asString(propRecord.action, ''),
        from: asString(propRecord.from, ''),
        to: asString(propRecord.to, ''),
      }
    }),
  }
}

function characterLabel(character: ScriptCharacter): string {
  const details = [
    character.name,
    character.aliases.length ? `别名：${character.aliases.join('、')}` : '',
    character.role,
  ].filter(Boolean)
  return details.length ? `${character.id}（${details.join(' / ')}）` : character.id
}

function namedEntityLabel(id: string, name: string): string {
  return name ? `${id}（${name}）` : id
}

function eventLabel(event: ScriptEvent): string {
  const summary = event.summary.length > 36 ? `${event.summary.slice(0, 36)}...` : event.summary
  return summary ? `${event.id}（${summary}）` : event.id
}

function entityLabel(id: string, labels: Map<string, string>): string {
  const normalizedId = id.trim()
  return labels.get(normalizedId) ?? (normalizedId || '空')
}

function entityLabels(ids: Set<string>, labels: Map<string, string>): string {
  if (ids.size === 0) return '空'
  return Array.from(ids)
    .sort()
    .map((id) => entityLabel(id, labels))
    .join('、')
}

function isNarratorCharacter(character: ScriptCharacter): boolean {
  return /旁白|叙述者|画外音|narrator/i.test(
    [character.name, character.role, character.description, ...character.aliases].join(' '),
  )
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

function asNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}
