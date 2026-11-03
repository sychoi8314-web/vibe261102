import type { Metadata } from "next"

import { createPostAction } from "@/app/actions"
import { PostForm } from "@/components/post-form"

export const metadata: Metadata = { title: "글쓰기" }

export default function NewPostPage() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">글쓰기</h1>
      <PostForm
        action={createPostAction}
        submitLabel="등록"
        cancelHref="/"
        passwordHint="글을 수정하거나 삭제할 때 필요합니다."
      />
    </div>
  )
}
