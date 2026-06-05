import type { Chapter } from './chapters'
import type { StoryElementsResponse } from './story-elements'

export interface ScriptYamlResponse {
  yaml: string
}

export async function generateScriptYaml(
  title: string,
  chapters: Chapter[],
  storyElements: StoryElementsResponse,
): Promise<ScriptYamlResponse> {
  const response = await fetch('/api/novels/script-yaml', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title,
      chapters,
      characters: storyElements.characters,
      locations: storyElements.locations,
      events: storyElements.events,
    }),
  })

  const payload = await response.json()

  if (!response.ok) {
    throw new Error(payload.detail ?? '剧本 YAML 生成失败')
  }

  return payload
}
