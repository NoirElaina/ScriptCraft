import type { Chapter } from './chapters'

export interface StoryCharacter {
  id: string
  name: string
  aliases: string[]
  role: string
  description: string
  motivation: string
}

export interface StoryLocation {
  id: string
  name: string
  description: string
}

export interface StoryEvent {
  id: string
  source_chapter: string
  summary: string
  involved_characters: string[]
}

export interface StoryElementsResponse {
  title: string
  characters: StoryCharacter[]
  locations: StoryLocation[]
  events: StoryEvent[]
}

export async function extractStoryElements(
  title: string,
  chapters: Chapter[],
): Promise<StoryElementsResponse> {
  const response = await fetch('/api/novels/story-elements', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title, chapters }),
  })

  const payload = await response.json()

  if (!response.ok) {
    throw new Error(payload.detail ?? '故事元素抽取失败')
  }

  return payload
}
