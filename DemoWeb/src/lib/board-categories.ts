export const CATEGORIES = {
  notice: "공지",
  free: "자유",
  qna: "질문",
} as const

export type Category = keyof typeof CATEGORIES

export function isCategory(value: unknown): value is Category {
  return typeof value === "string" && value in CATEGORIES
}
