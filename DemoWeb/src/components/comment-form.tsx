"use client"

import { useActionState, useEffect } from "react"
import { toast } from "sonner"

import { addCommentAction } from "@/app/actions"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

export function CommentForm({ postId }: { postId: number }) {
  const [state, formAction, pending] = useActionState(
    addCommentAction.bind(null, postId),
    {}
  )

  useEffect(() => {
    if (state.ok) toast.success("댓글이 등록되었습니다.")
  }, [state])

  return (
    <form
      action={formAction}
      className="flex flex-col gap-2 rounded-xl border p-4"
    >
      <Input
        name="author"
        required
        maxLength={20}
        placeholder="작성자"
        aria-label="작성자"
        className="sm:w-48"
      />
      <Textarea
        name="content"
        required
        maxLength={1000}
        placeholder="댓글을 입력하세요"
        aria-label="댓글 내용"
      />
      <div className="flex items-center justify-between gap-2">
        <p role="alert" className="text-sm text-destructive">
          {state.error}
        </p>
        <Button type="submit" disabled={pending}>
          {pending ? "등록 중..." : "댓글 등록"}
        </Button>
      </div>
    </form>
  )
}
