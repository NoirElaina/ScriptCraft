export function normalizeNovelText(text: string): string {
  return text
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.replace(/[ \t\u3000]+$/g, ''))
    .join('\n')
    .replace(/\n[ \t\u3000]*\n(?:[ \t\u3000]*\n)+/g, '\n\n')
    .replace(/^[ \t\u3000\n]+/, '')
    .replace(/[ \t\u3000\n]+$/, '')
}
