"use client"

import { useActionState } from "react"
import { Trash2Icon } from "lucide-react"

import { deletePostAction } from "@/app/actions"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function DeletePostDialog({ postId }: { postId: number }) {
  const [state, formAction, pending] = useActionState(
    deletePostAction.bind(null, postId),
    {}
  )

  return (
    <AlertDialog>
      <AlertDialogTrigger render={<Button variant="destructive" />}>
        <Trash2Icon data-icon="inline-start" />
        삭제
      </AlertDialogTrigger>
      <AlertDialogContent>
        <form action={formAction} className="contents">
          <AlertDialogHeader>
            <AlertDialogTitle>글을 삭제할까요?</AlertDialogTitle>
            <AlertDialogDescription>
              삭제한 글은 복구할 수 없습니다. 작성 시 입력한 비밀번호를
              입력하세요.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex flex-col gap-2">
            <Input
              name="password"
              type="password"
              required
              autoFocus
              autoComplete="off"
              placeholder="비밀번호"
              aria-label="비밀번호"
            />
            {state.error && (
              <p role="alert" className="text-sm text-destructive">
                {state.error}
              </p>
            )}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <Button type="submit" variant="destructive" disabled={pending}>
              {pending ? "삭제 중..." : "삭제"}
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  )
}
