import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto"
import { neon } from "@neondatabase/serverless"
import { connection } from "next/server"

import type { Category } from "@/lib/board-categories"

export { CATEGORIES, isCategory, type Category } from "@/lib/board-categories"

export type Comment = {
  id: number
  author: string
  content: string
  createdAt: string
}

export type Post = {
  id: number
  category: Category
  title: string
  content: string
  author: string
  createdAt: string
  updatedAt: string | null
  views: number
  comments: Comment[]
}

export type PostSummary = Omit<Post, "content" | "comments"> & {
  commentCount: number
}

export const PAGE_SIZE = 10

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is not set. Add it to .env.local.")
}
const sql = neon(process.env.DATABASE_URL)

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

// ---- row mapping ----

type Row = Record<string, unknown>

function iso(value: unknown) {
  return new Date(value as string | Date).toISOString()
}

function toSummary(row: Row): PostSummary {
  return {
    id: row.id as number,
    category: row.category as Category,
    title: row.title as string,
    author: row.author as string,
    createdAt: iso(row.created_at),
    updatedAt: row.updated_at ? iso(row.updated_at) : null,
    views: row.views as number,
    commentCount: row.comment_count as number,
  }
}

function toComment(row: Row): Comment {
  return {
    id: row.id as number,
    author: row.author as string,
    content: row.content as string,
    createdAt: iso(row.created_at),
  }
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
  // Escape LIKE wildcards so the search term is matched literally.
  const pattern = query?.trim()
    ? `%${query.trim().replace(/[\\%_]/g, "\\$&")}%`
    : null
  const where = `
    WHERE ($1::text IS NULL OR p.category = $1)
      AND ($2::text IS NULL OR p.title ILIKE $2 OR p.content ILIKE $2 OR p.author ILIKE $2)`
  const filter = [category ?? null, pattern]

  const [{ total }] = await sql.query(
    `SELECT count(*)::int AS total FROM posts p ${where}`,
    filter
  )
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const current = Math.min(Math.max(1, page), totalPages)

  const rows = await sql.query(
    `SELECT p.id, p.category, p.title, p.author, p.created_at, p.updated_at, p.views,
            (SELECT count(*)::int FROM comments c WHERE c.post_id = p.id) AS comment_count
       FROM posts p ${where}
      ORDER BY p.id DESC
      LIMIT $3 OFFSET $4`,
    [...filter, PAGE_SIZE, (current - 1) * PAGE_SIZE]
  )

  return {
    posts: rows.map(toSummary),
    total: total as number,
    page: current,
    totalPages,
  }
}

export async function getPost(id: number): Promise<Post | null> {
  await connection()
  const [postRows, commentRows] = await Promise.all([
    sql`SELECT id, category, title, content, author, created_at, updated_at, views
          FROM posts WHERE id = ${id}`,
    sql`SELECT id, author, content, created_at
          FROM comments WHERE post_id = ${id} ORDER BY id`,
  ])
  const row = postRows[0]
  if (!row) return null
  return {
    ...toSummary({ ...row, comment_count: commentRows.length }),
    content: row.content as string,
    comments: commentRows.map(toComment),
  }
}

// ---- mutations ----

export type PostInput = {
  category: Category
  title: string
  content: string
  author: string
}

export async function createPost(input: PostInput & { password: string }) {
  const [{ id }] = await sql`
    INSERT INTO posts (category, title, content, author, password_hash)
    VALUES (${input.category}, ${input.title}, ${input.content}, ${input.author},
            ${hashPassword(input.password)})
    RETURNING id`
  return id as number
}

type MutationResult = "ok" | "not-found" | "wrong-password"

async function checkPassword(
  id: number,
  password: string
): Promise<MutationResult> {
  const [row] = await sql`SELECT password_hash FROM posts WHERE id = ${id}`
  if (!row) return "not-found"
  return verifyPassword(password, row.password_hash as string)
    ? "ok"
    : "wrong-password"
}

export async function updatePost(
  id: number,
  password: string,
  input: PostInput
): Promise<MutationResult> {
  const result = await checkPassword(id, password)
  if (result !== "ok") return result
  await sql`
    UPDATE posts
       SET category = ${input.category}, title = ${input.title},
           content = ${input.content}, author = ${input.author},
           updated_at = now()
     WHERE id = ${id}`
  return "ok"
}

export async function deletePost(
  id: number,
  password: string
): Promise<MutationResult> {
  const result = await checkPassword(id, password)
  if (result !== "ok") return result
  await sql`DELETE FROM posts WHERE id = ${id}`
  return "ok"
}

export async function addComment(
  postId: number,
  input: { author: string; content: string }
): Promise<boolean> {
  const rows = await sql`
    INSERT INTO comments (post_id, author, content)
    SELECT id, ${input.author}, ${input.content} FROM posts WHERE id = ${postId}
    RETURNING id`
  return rows.length > 0
}

export async function incrementViews(postId: number) {
  await sql`UPDATE posts SET views = views + 1 WHERE id = ${postId}`
}
