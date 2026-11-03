"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

import * as board from "@/lib/board"

export type PostFormValues = {
  category: string
  title: string
  content: string
  author: string
}

export type PostFormState = {
  error?: string
  values?: PostFormValues
}

export type SimpleFormState = { error?: string; ok?: boolean }

const LIMITS = { title: 100, author: 20, content: 10000, comment: 1000 }

function text(formData: FormData, name: string) {
  const value = formData.get(name)
  return typeof value === "string" ? value.trim() : ""
}

function parsePostForm(formData: FormData) {
  const values: PostFormValues = {
    category: text(formData, "category"),
    title: text(formData, "title"),
    content: text(formData, "content"),
    author: text(formData, "author"),
  }
  const password = formData.get("password")?.toString() ?? ""

  let error: string | undefined
  if (!board.isCategory(values.category)) error = "분류를 선택해 주세요."
  else if (!values.title) error = "제목을 입력해 주세요."
  else if (values.title.length > LIMITS.title)
    error = `제목은 ${LIMITS.title}자 이내로 입력해 주세요.`
  else if (!values.author) error = "작성자를 입력해 주세요."
  else if (values.author.length > LIMITS.author)
    error = `작성자는 ${LIMITS.author}자 이내로 입력해 주세요.`
  else if (!values.content) error = "내용을 입력해 주세요."
  else if (values.content.length > LIMITS.content)
    error = `내용은 ${LIMITS.content}자 이내로 입력해 주세요.`
  else if (password.length < 4) error = "비밀번호는 4자 이상 입력해 주세요."

  return { values, password, error }
}

export async function createPostAction(
  _prev: PostFormState,
  formData: FormData
): Promise<PostFormState> {
  const { values, password, error } = parsePostForm(formData)
  if (error) return { error, values }

  const id = await board.createPost({
    ...values,
    category: values.category as board.Category,
    password,
  })
  revalidatePath("/")
  redirect(`/posts/${id}`)
}

export async function updatePostAction(
  id: number,
  _prev: PostFormState,
  formData: FormData
): Promise<PostFormState> {
  const { values, password, error } = parsePostForm(formData)
  if (error) return { error, values }

  const result = await board.updatePost(id, password, {
    ...values,
    category: values.category as board.Category,
  })
  if (result === "not-found") return { error: "글을 찾을 수 없습니다.", values }
  if (result === "wrong-password")
    return { error: "비밀번호가 일치하지 않습니다.", values }

  revalidatePath("/")
  revalidatePath(`/posts/${id}`)
  redirect(`/posts/${id}`)
}

export async function deletePostAction(
  id: number,
  _prev: SimpleFormState,
  formData: FormData
): Promise<SimpleFormState> {
  const password = formData.get("password")?.toString() ?? ""
  if (!password) return { error: "비밀번호를 입력해 주세요." }

  const result = await board.deletePost(id, password)
  if (result === "wrong-password")
    return { error: "비밀번호가 일치하지 않습니다." }

  revalidatePath("/")
  redirect("/")
}

export async function addCommentAction(
  postId: number,
  _prev: SimpleFormState,
  formData: FormData
): Promise<SimpleFormState> {
  const author = text(formData, "author")
  const content = text(formData, "content")
  if (!author) return { error: "작성자를 입력해 주세요." }
  if (author.length > LIMITS.author)
    return { error: `작성자는 ${LIMITS.author}자 이내로 입력해 주세요.` }
  if (!content) return { error: "댓글 내용을 입력해 주세요." }
  if (content.length > LIMITS.comment)
    return { error: `댓글은 ${LIMITS.comment}자 이내로 입력해 주세요.` }

  if (!(await board.addComment(postId, { author, content })))
    return { error: "글을 찾을 수 없습니다." }

  revalidatePath(`/posts/${postId}`)
  return { ok: true }
}

export async function incrementViewsAction(postId: number) {
  await board.incrementViews(postId)
}
