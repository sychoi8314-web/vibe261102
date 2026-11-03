import { Suspense } from "react"
import type { Metadata } from "next"
import { notFound } from "next/navigation"

import { updatePostAction } from "@/app/actions"
import { getPost } from "@/lib/board"
import { PostForm } from "@/components/post-form"

export const metadata: Metadata = { title: "글 수정" }

export default function EditPostPage({ params }: PageProps<"/posts/[id]/edit">) {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">글 수정</h1>
      <Suspense
        fallback={<div className="h-96 animate-pulse rounded-xl bg-muted" />}
      >
        <EditForm params={params} />
      </Suspense>
    </div>
  )
}

async function EditForm({
  params,
}: {
  params: PageProps<"/posts/[id]/edit">["params"]
}) {
  const id = Number((await params).id)
  const post = Number.isInteger(id) ? await getPost(id) : null
  if (!post) notFound()

  return (
    <PostForm
      action={updatePostAction.bind(null, post.id)}
      defaults={{
        category: post.category,
        title: post.title,
        content: post.content,
        author: post.author,
      }}
      submitLabel="수정 완료"
      cancelHref={`/posts/${post.id}`}
      passwordHint="글을 작성할 때 입력한 비밀번호를 입력하세요."
    />
  )
}
