import { marked, type Token, type Tokens } from 'marked'
import { theme } from '../theme.js'

export type MarkdownRenderLine = {
  text: string
  color: string
  bold?: boolean
}

type RenderOptions = {
  color: string
  columns: number
}

type TokenLike = Token & Record<string, unknown>

const MIN_COLUMN_WIDTH = 4
const MAX_ROW_LINES = 4
const TABLE_MARGIN = 4
const TABLE_LINE = '\u2500'
const TABLE_VERTICAL = '\u2502'
const TABLE_TOP_LEFT = '\u250c'
const TABLE_TOP_JOIN = '\u252c'
const TABLE_TOP_RIGHT = '\u2510'
const TABLE_MIDDLE_LEFT = '\u251c'
const TABLE_MIDDLE_JOIN = '\u253c'
const TABLE_MIDDLE_RIGHT = '\u2524'
const TABLE_BOTTOM_LEFT = '\u2514'
const TABLE_BOTTOM_JOIN = '\u2534'
const TABLE_BOTTOM_RIGHT = '\u2518'
const BLOCKQUOTE_BAR = '\u2502'

let markedConfigured = false

export function renderMarkdownLines(text: string, options: RenderOptions): MarkdownRenderLine[] {
  configureMarked()
  const tokens = marked.lexer(text)
  const lines = renderTokens(tokens, options, 0)
  return lines.length > 0 ? lines : [{ text: '', color: theme.subtle }]
}

function configureMarked() {
  if (markedConfigured) return
  markedConfigured = true
  marked.use({
    tokenizer: {
      del() {
        return undefined
      },
    },
  })
}

function renderTokens(tokens: Token[], options: RenderOptions, listDepth: number): MarkdownRenderLine[] {
  const lines: MarkdownRenderLine[] = []
  for (const token of tokens) {
    lines.push(...renderToken(token, options, listDepth))
  }
  return trimOuterBlankLines(lines)
}

function renderToken(token: Token, options: RenderOptions, listDepth: number): MarkdownRenderLine[] {
  switch (token.type) {
    case 'space':
      return [{ text: '', color: theme.subtle }]
    case 'hr':
      return [{ text: TABLE_LINE.repeat(Math.min(Math.max(12, options.columns - 2), 72)), color: theme.muted }]
    case 'heading':
      return wrapLine(inlineText((token as Tokens.Heading).tokens), {
        columns: options.columns,
        color: theme.assistant,
        bold: true,
      })
    case 'paragraph':
      return wrapLine(inlineText((token as Tokens.Paragraph).tokens), {
        columns: options.columns,
        color: options.color,
      })
    case 'text': {
      const textToken = token as Tokens.Text
      return wrapLine(textToken.tokens ? inlineText(textToken.tokens) : textToken.text, {
        columns: options.columns,
        color: options.color,
      })
    }
    case 'blockquote':
      return renderBlockquote(token as Tokens.Blockquote, options, listDepth)
    case 'code':
      return renderCode(token as Tokens.Code, options)
    case 'list':
      return renderList(token as Tokens.List, options, listDepth)
    case 'table':
      return renderTableToken(token as Tokens.Table, options)
    case 'html':
    case 'def':
      return []
    default:
      return wrapLine(token.raw ?? '', { columns: options.columns, color: options.color })
  }
}

function renderBlockquote(token: Tokens.Blockquote, options: RenderOptions, listDepth: number) {
  const inner = renderTokens(token.tokens ?? [], options, listDepth)
  return inner.map(line => ({
    ...line,
    text: line.text ? `${BLOCKQUOTE_BAR} ${line.text}` : BLOCKQUOTE_BAR,
    color: line.color === theme.subtle ? theme.muted : line.color,
  }))
}

function renderCode(token: Tokens.Code, options: RenderOptions) {
  const language = token.lang ? ` ${token.lang}` : ''
  const lines: MarkdownRenderLine[] = [
    { text: `${TABLE_TOP_LEFT}${TABLE_LINE.repeat(Math.min(12 + language.length, options.columns - 2))}${language}`, color: theme.muted },
  ]
  for (const line of token.text.split(/\r?\n/)) {
    lines.push(...wrapLine(`  ${line}`, { columns: options.columns, color: theme.cwd }))
  }
  lines.push({ text: TABLE_BOTTOM_LEFT + TABLE_LINE.repeat(Math.min(16, options.columns - 2)), color: theme.muted })
  return lines
}

function renderList(token: Tokens.List, options: RenderOptions, listDepth: number) {
  const lines: MarkdownRenderLine[] = []
  const start = Number(token.start ?? 1)
  token.items.forEach((item, index) => {
    const marker = token.ordered ? `${start + index}.` : '-'
    lines.push(...renderListItem(item, marker, options, listDepth))
  })
  return lines
}

function renderListItem(item: Tokens.ListItem, marker: string, options: RenderOptions, listDepth: number) {
  const indent = '  '.repeat(listDepth)
  const childLines = renderTokens(item.tokens ?? [{ type: 'text', raw: item.text, text: item.text } as Token], {
    ...options,
    columns: Math.max(20, options.columns - indent.length - marker.length - 1),
  }, listDepth + 1)
  if (childLines.length === 0) {
    return [{ text: `${indent}${marker}`, color: options.color }]
  }
  return childLines.map((line, index) => ({
    ...line,
    text: index === 0
      ? `${indent}${marker} ${line.text}`
      : `${indent}${' '.repeat(marker.length + 1)}${line.text}`,
  }))
}

function renderTableToken(token: Tokens.Table, options: RenderOptions) {
  const header = token.header.map(cellText)
  const rows = token.rows.map(row => row.map(cellText))
  return renderTable([header, ...rows], options.columns, options.color)
}

function cellText(cell: Tokens.TableCell) {
  return inlineText(cell.tokens ?? [])
}

function inlineText(tokens: Token[] | undefined): string {
  if (!tokens) return ''
  return tokens.map(token => inlineTokenText(token)).join('')
}

function inlineTokenText(token: Token): string {
  const typed = token as TokenLike
  switch (token.type) {
    case 'codespan':
    case 'escape':
      return String(typed.text ?? '')
    case 'strong':
    case 'em':
    case 'del':
      return inlineText(typed.tokens as Token[] | undefined)
    case 'link': {
      const href = String(typed.href ?? '')
      if (href.startsWith('mailto:')) return href.replace(/^mailto:/, '')
      const label = inlineText(typed.tokens as Token[] | undefined) || href
      return label === href ? href : `${label} (${href})`
    }
    case 'image':
      return String(typed.href ?? typed.text ?? '')
    case 'br':
      return '\n'
    case 'text':
      return typed.tokens ? inlineText(typed.tokens as Token[]) : String(typed.text ?? '')
    default:
      return String(typed.raw ?? typed.text ?? '')
  }
}

function renderTable(rows: string[][], columns: number, color: string): MarkdownRenderLine[] {
  const columnCount = Math.max(...rows.map(row => row.length))
  const normalized = rows.map(row =>
    Array.from({ length: columnCount }, (_, column) => row[column] ?? ''),
  )
  const available = Math.max(columnCount * MIN_COLUMN_WIDTH, columns - TABLE_MARGIN - 1 - columnCount * 3)
  const idealWidths = Array.from({ length: columnCount }, (_, column) =>
    Math.max(MIN_COLUMN_WIDTH, ...normalized.map(row => displayWidth(row[column] ?? ''))),
  )
  const minWidths = Array.from({ length: columnCount }, (_, column) =>
    Math.max(MIN_COLUMN_WIDTH, ...normalized.map(row => longestWordWidth(row[column] ?? ''))),
  )
  const totalIdeal = sum(idealWidths)
  const totalMin = sum(minWidths)
  let hardWrap = false
  let widths: number[]

  if (totalIdeal <= available) {
    widths = idealWidths
  } else if (totalMin <= available) {
    const remaining = available - totalMin
    const overflow = idealWidths.map((width, index) => width - minWidths[index]!)
    const totalOverflow = sum(overflow)
    widths = minWidths.map((width, index) =>
      width + (totalOverflow === 0 ? 0 : Math.floor((overflow[index]! / totalOverflow) * remaining)),
    )
  } else {
    hardWrap = true
    const width = Math.max(MIN_COLUMN_WIDTH, Math.floor(available / columnCount))
    widths = Array.from({ length: columnCount }, () => width)
  }

  const maxLines = Math.max(...normalized.flatMap(row =>
    row.map((cell, column) => wrapByWidth(cell, widths[column]!, hardWrap).length),
  ))
  if (maxLines > MAX_ROW_LINES || columns < 48) {
    return renderVerticalTable(normalized, columns, color)
  }

  const output: MarkdownRenderLine[] = []
  output.push({ text: border('top', widths), color: theme.muted })
  output.push(...rowLines(normalized[0] ?? [], widths, true, color, hardWrap))
  output.push({ text: border('middle', widths), color: theme.muted })
  for (const row of normalized.slice(1)) {
    output.push(...rowLines(row, widths, false, color, hardWrap))
  }
  output.push({ text: border('bottom', widths), color: theme.muted })
  return output
}

function renderVerticalTable(rows: string[][], columns: number, color: string): MarkdownRenderLine[] {
  const [headers = [], ...body] = rows
  const separator = TABLE_LINE.repeat(Math.min(Math.max(8, columns - 8), 48))
  const output: MarkdownRenderLine[] = []
  for (const [rowIndex, row] of body.entries()) {
    if (rowIndex > 0) output.push({ text: separator, color: theme.muted })
    row.forEach((cell, column) => {
      const label = headers[column] || `Column ${column + 1}`
      output.push(...wrapLine(`${label}: ${cell}`, {
        columns,
        color,
        bold: column === 0,
      }))
    })
  }
  return output
}

function rowLines(row: string[], widths: number[], header: boolean, color: string, hardWrap: boolean) {
  const cells = row.map((cell, column) => wrapByWidth(cell, widths[column]!, hardWrap))
  const height = Math.max(...cells.map(cell => cell.length), 1)
  const output: MarkdownRenderLine[] = []
  for (let lineIndex = 0; lineIndex < height; lineIndex += 1) {
    const text = `${TABLE_VERTICAL} ${cells.map((cell, column) =>
      padAligned(cell[lineIndex] ?? '', widths[column]!, header ? 'center' : 'left'),
    ).join(` ${TABLE_VERTICAL} `)} ${TABLE_VERTICAL}`
    output.push({ text, color, bold: header })
  }
  return output
}

function border(kind: 'top' | 'middle' | 'bottom', widths: number[]) {
  const pieces = {
    top: [TABLE_TOP_LEFT, TABLE_TOP_JOIN, TABLE_TOP_RIGHT],
    middle: [TABLE_MIDDLE_LEFT, TABLE_MIDDLE_JOIN, TABLE_MIDDLE_RIGHT],
    bottom: [TABLE_BOTTOM_LEFT, TABLE_BOTTOM_JOIN, TABLE_BOTTOM_RIGHT],
  }[kind]
  return `${pieces[0]}${widths.map(width => TABLE_LINE.repeat(width + 2)).join(pieces[1])}${pieces[2]}`
}

function wrapLine(
  text: string,
  options: { columns: number; color: string; bold?: boolean },
): MarkdownRenderLine[] {
  const source = text.split(/\r?\n/)
  return source.flatMap((line, index) => {
    const wrapped = wrapByWidth(line, Math.max(20, options.columns), true).map(segment => ({
      text: segment,
      color: options.color,
      bold: options.bold,
    }))
    return index === 0 ? wrapped : [{ text: '', color: theme.subtle }, ...wrapped]
  })
}

function wrapByWidth(text: string, width: number, hard: boolean) {
  if (!text) return ['']
  const result: string[] = []
  let line = ''
  for (const word of text.split(/(\s+)/)) {
    if (!word) continue
    if (/^\s+$/.test(word)) {
      if (line && displayWidth(line) < width) line += ' '
      continue
    }
    if (displayWidth(line + word) <= width) {
      line += word
      continue
    }
    if (line) result.push(line.trimEnd())
    if (!hard || displayWidth(word) <= width) {
      line = word
      continue
    }
    let chunk = ''
    for (const char of [...word]) {
      if (displayWidth(chunk + char) > width) {
        result.push(chunk)
        chunk = char
      } else {
        chunk += char
      }
    }
    line = chunk
  }
  if (line || result.length === 0) result.push(line.trimEnd())
  return result
}

function padAligned(text: string, width: number, align: 'left' | 'center') {
  const padding = Math.max(0, width - displayWidth(text))
  if (align === 'left') return `${text}${' '.repeat(padding)}`
  const left = Math.floor(padding / 2)
  return `${' '.repeat(left)}${text}${' '.repeat(padding - left)}`
}

function longestWordWidth(text: string) {
  const words = text.split(/\s+/).filter(Boolean)
  if (words.length === 0) return MIN_COLUMN_WIDTH
  return Math.max(...words.map(displayWidth), MIN_COLUMN_WIDTH)
}

function trimOuterBlankLines(lines: MarkdownRenderLine[]) {
  let start = 0
  let end = lines.length
  while (start < end && !lines[start]?.text) start += 1
  while (end > start && !lines[end - 1]?.text) end -= 1
  return lines.slice(start, end)
}

function sum(values: number[]) {
  return values.reduce((total, value) => total + value, 0)
}

function displayWidth(text: string) {
  return [...text].reduce((width, char) => width + (char.charCodeAt(0) > 127 ? 2 : 1), 0)
}
