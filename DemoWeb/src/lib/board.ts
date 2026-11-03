import { promises as fs } from "node:fs"
import path from "node:path"
import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto"
import { connection } from "next/server"

import type { Category } from "@/lib/board-categories"

export { CATEGORIES, isCategory, type Category } from "@/lib/board-categories"

export type Comment = {
  id: number
  author: string
  content: string
  createdAt: string
}

type StoredPost = {
  id: number
  category: Category
  title: string
  content: string
  author: string
  passwordHash: string
  createdAt: string
  updatedAt: string | null
  views: number
  comments: Comment[]
}

type Store = {
  nextPostId: number
  nextCommentId: number
  posts: StoredPost[]
}

export type Post = Omit<StoredPost, "passwordHash">
export type PostSummary = Omit<Post, "content" | "comments"> & {
  commentCount: number
}

const DATA_FILE = path.join(process.cwd(), "data", "board.json")
export const PAGE_SIZE = 10

// ---- password helpers ----

function hashPassword(password: string) {
  const salt = randomBytes(16).toString("hex")
  const hash = scryptSync(password, salt, 32).toString("hex")
  return `${salt}:${hash}`
}

function verifyPassword(password: string, stored: string) {
  const [salt, hash] = stored.split(":")
  const expected = Buffer.from(hash, "hex")
  const actual = scryptSync(password, salt, expected.length)
  return timingSafeEqual(expected, actual)
}

// ---- file store ----

function seedStore(): Store {
  const now = Date.now()
  const at = (hoursAgo: number) =>
    new Date(now - hoursAgo * 60 * 60 * 1000).toISOString()
  const seed: Array<Omit<StoredPost, "id" | "passwordHash" | "updatedAt">> = [
    {
      category: "notice",
      title: "DemoWeb 게시판에 오신 것을 환영합니다",
      content:
        "자유롭게 글을 작성하고 댓글을 남겨 보세요.\n\n글을 쓸 때 입력한 비밀번호로 나중에 글을 수정하거나 삭제할 수 있습니다.\n(예시 글의 비밀번호는 모두 1234 입니다.)",
      author: "관리자",
      createdAt: at(72),
      views: 42,
      comments: [],
    },
    {
      category: "free",
      title: "Next.js 16 써보신 분 계신가요?",
      content:
        "Cache Components가 기본으로 켜져 있던데 다들 어떻게 쓰고 계신지 궁금합니다.",
      author: "개발자A",
      createdAt: at(30),
      views: 17,
      comments: [
        {
          id: 1,
          author: "개발자B",
          content: "Suspense 경계만 잘 잡으면 생각보다 편하더라고요.",
          createdAt: at(28),
        },
      ],
    },
    {
      category: "qna",
      title: "shadcn/ui 컴포넌트 커스터마이징 질문",
      content:
        "버튼 색상을 프로젝트 전체에서 바꾸고 싶은데 globals.css의 CSS 변수만 수정하면 되나요?",
      author: "질문러",
      createdAt: at(5),
      views: 8,
      comments: [],
    },
    {
      category: "free",
      title: "오늘 점심 뭐 드셨나요",
      content: "저는 김치찌개 먹었습니다 🍲",
      author: "배고픈사람",
      createdAt: at(1),
      views: 3,
      comments: [],
    },
  ]
  const passwordHash = hashPassword("1234")
  return {
    nextPostId: seed.length + 1,
    nextCommentId: 2,
    posts: seed.map((post, i) => ({
      ...post,
      id: i + 1,
      passwordHash,
      updatedAt: null,
    })),
  }
}

async function readStore(): Promise<Store> {
  try {
    return JSON.parse(await fs.readFile(DATA_FILE, "utf8")) as Store
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error
    const store = seedStore()
    await writeStore(store)
    return store
  }
}

async function writeStore(store: Store) {
  await fs.mkdir(path.dirname(DATA_FILE), { recursive: true })
  await fs.writeFile(DATA_FILE, JSON.stringify(store, null, 2), "utf8")
}

// Serialize read-modify-write cycles so concurrent requests don't clobber each other.
let queue: Promise<unknown> = Promise.resolve()

function mutate<T>(fn: (store: Store) => T): Promise<T> {
  const run = queue.then(async () => {
    const store = await readStore()
    const result = fn(store)
    await writeStore(store)
    return result
  })
  queue = run.catch(() => {})
  return run
}

function toPost(stored: StoredPost): Post {
  const post: Post & { passwordHash?: string } = { ...stored }
  delete post.passwordHash
  return post
}

// ---- queries (always read fresh data at request time) ----

export async function listPosts({
  category,
  query,
  page,
}: {
  category?: Category
  query?: string
  page: number
}) {
  await connection()
  const store = await readStore()
  const q = query?.trim().toLowerCase()
  const filtered = store.posts
    .filter((post) => !category || post.category === category)
    .filter(
      (post) =>
        !q ||
        post.title.toLowerCase().includes(q) ||
        post.content.toLowerCase().includes(q) ||
        post.author.toLowerCase().includes(q)
    )
    .sort((a, b) => b.id - a.id)

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const current = Math.min(Math.max(1, page), totalPages)
  const posts: PostSummary[] = filtered
    .slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE)
    .map((post) => ({
      id: post.id,
      category: post.category,
      title: post.title,
      author: post.author,
      createdAt: post.createdAt,
      updatedAt: post.updatedAt,
      views: post.views,
      commentCount: post.comments.length,
    }))

  return { posts, total: filtered.length, page: current, totalPages }
}

export async function getPost(id: number): Promise<Post | null> {
  await connection()
  const store = await readStore()
  const post = store.posts.find((p) => p.id === id)
  return post ? toPost(post) : null
}

// ---- mutations ----

export type PostInput = {
  category: Category
  title: string
  content: string
  author: string
}

export function createPost(input: PostInput & { password: string }) {
  return mutate((store) => {
    const { password, ...fields } = input
    const post: StoredPost = {
      ...fields,
      id: store.nextPostId++,
      passwordHash: hashPassword(password),
      createdAt: new Date().toISOString(),
      updatedAt: null,
      views: 0,
      comments: [],
    }
    store.posts.push(post)
    return post.id
  })
}

type MutationResult = "ok" | "not-found" | "wrong-password"

export function updatePost(
  id: number,
  password: string,
  input: PostInput
): Promise<MutationResult> {
  return mutate((store) => {
    const post = store.posts.find((p) => p.id === id)
    if (!post) return "not-found"
    if (!verifyPassword(password, post.passwordHash)) return "wrong-password"
    Object.assign(post, input, { updatedAt: new Date().toISOString() })
    return "ok"
  })
}

export function deletePost(
  id: number,
  password: string
): Promise<MutationResult> {
  return mutate((store) => {
    const index = store.posts.findIndex((p) => p.id === id)
    if (index === -1) return "not-found"
    if (!verifyPassword(password, store.posts[index].passwordHash))
      return "wrong-password"
    store.posts.splice(index, 1)
    return "ok"
  })
}

export function addComment(
  postId: number,
  input: { author: string; content: string }
): Promise<boolean> {
  return mutate((store) => {
    const post = store.posts.find((p) => p.id === postId)
    if (!post) return false
    post.comments.push({
      id: store.nextCommentId++,
      ...input,
      createdAt: new Date().toISOString(),
    })
    return true
  })
}

export function incrementViews(postId: number) {
  return mutate((store) => {
    const post = store.posts.find((p) => p.id === postId)
    if (post) post.views++
  })
}
