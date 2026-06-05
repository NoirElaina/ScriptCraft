export interface Chapter {
  id: string
  index: number
  heading: string
  title: string
  content: string
}

export interface ChapterParseResponse {
  chapter_count: number
  chapters: Chapter[]
}

export async function parseChapters(text: string): Promise<ChapterParseResponse> {
  const response = await fetch('/api/novels/chapters', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  })

  const payload = await response.json()

  if (!response.ok) {
    throw new Error(payload.detail ?? '章节解析失败')
  }

  return payload
}
