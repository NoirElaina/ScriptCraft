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
    return asArray(scriptDocument.value?.characters).map((item, index) => {
      const record = isRecord(item) ? item : {}
      return {
        id: asString(record.id, `char_${String(index + 1).padStart(3, '0')}`),
        name: asString(record.name, '未命名角色'),
        aliases: asStringArray(record.aliases),
        role: asString(record.role, ''),
        description: asString(record.description, ''),
        motivation: asString(record.motivation, ''),
      }
    })
  })

  const scriptLocations = computed<ScriptLocation[]>(() => {
    return asArray(scriptDocument.value?.locations).map((item, index) => {
      const record = isRecord(item) ? item : {}
      return {
        id: asString(record.id, `loc_${String(index + 1).padStart(3, '0')}`),
        name: asString(record.name, '未命名地点'),
        description: asString(record.description, ''),
      }
    })
  })

  const scriptEvents = computed<ScriptEvent[]>(() => {
    return asArray(scriptDocument.value?.events).map((item, index) => {
      const record = isRecord(item) ? item : {}
      return {
        id: asString(record.id, `event_${String(index + 1).padStart(3, '0')}`),
        source_chapter: asString(record.source_chapter, ''),
        summary: asString(record.summary, ''),
      }
    })
  })

  const scriptScenes = computed<ScriptScene[]>(() => {
    return asArray(scriptDocument.value?.scenes).map((item, index) => {
      const record = isRecord(item) ? item : {}
      return {
        id: asString(record.id, `scene_${String(index + 1).padStart(3, '0')}`),
        title: asString(record.title, `场次 ${index + 1}`),
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
            type: asString(beatRecord.type, 'action'),
            speaker_id: asString(beatRecord.speaker_id, ''),
            content: asString(beatRecord.content, ''),
          }
        }),
      }
    })
  })

  const scriptParseError = computed(() => Boolean(scriptYaml.value && !scriptDocument.value))

  const scriptValidationIssues = computed(() => {
    if (!scriptYaml.value.trim()) return []
    if (!scriptDocument.value) return ['YAML 解析失败']

    const issues: string[] = []
    const requiredKeys = ['schema_version', 'title', 'metadata', 'characters', 'locations', 'events', 'scenes']
    for (const key of requiredKeys) {
      if (!(key in scriptDocument.value)) {
        issues.push(`缺少顶层字段：${key}`)
      }
    }
    if (!scriptScenes.value.length) {
      issues.push('至少需要包含一个 scene')
    }
    for (const scene of scriptScenes.value) {
      if (!scene.beats.length) {
        issues.push(`${scene.id} 至少需要包含一个 beat`)
      }
      for (const beat of scene.beats) {
        if (beat.type === 'dialogue' && !beat.speaker_id) {
          issues.push(`${scene.id} 的 dialogue beat 缺少 speaker_id`)
        }
      }
    }
    return issues
  })

  const characterNameById = computed(() => {
    return new Map(scriptCharacters.value.map((character) => [character.id, character.name]))
  })

  const locationNameById = computed(() => {
    return new Map(scriptLocations.value.map((location) => [location.id, location.name]))
  })

  const eventSummaryById = computed(() => {
    return new Map(scriptEvents.value.map((event) => [event.id, event.summary]))
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
    metadataValue,
    characterName,
    locationName,
    eventSummary,
    beatTypeLabel,
    beatTypeClass,
  }
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
