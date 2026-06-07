import type {
  ScriptCharacter,
  ScriptLocation,
  ScriptScene,
  ScriptStoryboardAction,
  ScriptStoryboardCamera,
  ScriptStoryboardCastMember,
  ScriptStoryboardProp,
  ScriptStoryboardScene,
} from '@/composables/useScriptYamlDocument'

export type StoryboardShotType = 'dialogue' | 'action' | 'narration' | 'transition' | 'sound'

export interface StoryboardActor {
  id: string
  name: string
  role: string
  description: string
  motivation: string
  color: number
  position: string
  pose: string
}

export interface StoryboardSetting {
  mood: string
  weather: string
  lighting: string
  background: string
}

export interface StoryboardFrame {
  id: string
  sceneId: string
  sourceBeatId: string
  type: StoryboardShotType
  label: string
  content: string
  speakerId: string
  speakerName: string
  durationMs: number
  camera: ScriptStoryboardCamera
  actions: ScriptStoryboardAction[]
  effects: string[]
  props: ScriptStoryboardProp[]
}

export interface StoryboardScenePlayback {
  id: string
  title: string
  summary: string
  locationName: string
  timeOfDay: string
  dramaticPurpose: string
  setting: StoryboardSetting
  actors: StoryboardActor[]
  frames: StoryboardFrame[]
}

export function buildStoryboardScenes(input: {
  characters: ScriptCharacter[]
  locations: ScriptLocation[]
  scenes: ScriptScene[]
  storyboardScenes: ScriptStoryboardScene[]
}): StoryboardScenePlayback[] {
  const characterById = new Map(input.characters.map((character) => [character.id, character]))
  const locationById = new Map(input.locations.map((location) => [location.id, location]))
  const sceneById = new Map(input.scenes.map((scene) => [scene.id, scene]))

  return input.storyboardScenes.flatMap((storyboardScene) => {
    const scene = sceneById.get(storyboardScene.scene_id)
    if (!scene) return []

    const beatById = new Map(scene.beats.map((beat) => [beat.id, beat]))
    const actors = storyboardScene.cast
      .map((member, index) => buildActor(member, index, characterById))
      .filter((actor): actor is StoryboardActor => Boolean(actor))

    return [
      {
        id: scene.id,
        title: scene.title,
        summary: scene.summary,
        locationName: locationById.get(scene.location_id)?.name || scene.location_id,
        timeOfDay: scene.time_of_day,
        dramaticPurpose: scene.dramatic_purpose,
        setting: {
          mood: storyboardScene.setting.mood,
          weather: storyboardScene.setting.weather,
          lighting: storyboardScene.setting.lighting,
          background: storyboardScene.setting.background,
        },
        actors,
        frames: storyboardScene.timeline.map((shot, shotIndex) => {
          const sourceBeat = beatById.get(shot.source_beat_id)
          const type = normalizeShotType(shot.type)
          const speakerId = shot.dialogue?.speaker_id || sourceBeat?.speaker_id || ''
          const speaker = speakerId ? characterById.get(speakerId) : undefined
          const content =
            type === 'dialogue'
              ? shot.dialogue?.text || sourceBeat?.content || ''
              : sourceBeat?.content || shot.actions.map((action) => action.motion).join('、')

          return {
            id: shot.id || `${scene.id}-shot-${shotIndex + 1}`,
            sceneId: scene.id,
            sourceBeatId: shot.source_beat_id,
            type,
            label: storyboardShotLabel(type),
            content,
            speakerId,
            speakerName: speaker?.name || speakerId,
            durationMs: Math.max(600, shot.duration_ms),
            camera: shot.camera,
            actions: shot.actions,
            effects: shot.effects,
            props: shot.props,
          }
        }),
      },
    ]
  })
}

export function storyboardShotLabel(type: string): string {
  const labels: Record<string, string> = {
    dialogue: '对白',
    action: '动作',
    narration: '旁白',
    transition: '转场',
    sound: '声音',
  }
  return labels[type] ?? type
}

function buildActor(
  member: ScriptStoryboardCastMember,
  index: number,
  characterById: Map<string, ScriptCharacter>,
): StoryboardActor | undefined {
  const character = characterById.get(member.character_id)
  if (!character) return undefined

  return {
    id: character.id,
    name: character.name,
    role: character.role,
    description: character.description,
    motivation: character.motivation,
    color: actorColor(character.id, index),
    position: member.position,
    pose: member.pose,
  }
}

function normalizeShotType(type: string): StoryboardShotType {
  if (type === 'dialogue' || type === 'action' || type === 'narration' || type === 'transition' || type === 'sound') {
    return type
  }
  return 'action'
}

function actorColor(actorId: string, index: number): number {
  const palette = [
    0x2563eb,
    0x059669,
    0xdc2626,
    0x7c3aed,
    0xca8a04,
    0x0f766e,
    0xc2410c,
    0x4f46e5,
  ]
  let hash = index
  for (const character of actorId) {
    hash = (hash * 31 + character.charCodeAt(0)) % palette.length
  }
  return palette[Math.abs(hash) % palette.length] ?? 0x2563eb
}
