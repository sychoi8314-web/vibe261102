"use client"

import { useActionState } from "react"
import Link from "next/link"

import type { PostFormState, PostFormValues } from "@/app/actions"
import { CATEGORIES } from "@/lib/board-categories"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

export function PostForm({
  action,
  defaults,
  submitLabel,
  cancelHref,
  passwordHint,
}: {
  action: (state: PostFormState, formData: FormData) => Promise<PostFormState>
  defaults?: PostFormValues
  submitLabel: string
  cancelHref: string
  passwordHint: string
}) {
  const [state, formAction, pending] = useActionState(action, {})
  const values = state.values ?? defaults

  return (
    <Card>
      <form action={formAction}>
        <CardContent className="flex flex-col gap-5">
          <div className="grid gap-5 sm:grid-cols-[10rem_1fr]">
            <div className="flex flex-col gap-2">
              <Label htmlFor="category">분류</Label>
              <select
                id="category"
                name="category"
                defaultValue={values?.category ?? "free"}
                className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
              >
                {Object.entries(CATEGORIES).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="title">제목</Label>
              <Input
                id="title"
                name="title"
                required
                maxLength={100}
                defaultValue={values?.title}
                placeholder="제목을 입력하세요"
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="content">내용</Label>
            <Textarea
              id="content"
              name="content"
              required
              maxLength={10000}
              defaultValue={values?.content}
              placeholder="내용을 입력하세요"
              className="min-h-64"
            />
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="author">작성자</Label>
              <Input
                id="author"
                name="author"
                required
                maxLength={20}
                defaultValue={values?.author}
                placeholder="닉네임"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">비밀번호</Label>
              <Input
                id="password"
                name="password"
                type="password"
                required
                minLength={4}
                autoComplete="off"
                placeholder="4자 이상"
              />
              <p className="text-xs text-muted-foreground">{passwordHint}</p>
            </div>
          </div>

          {state.error && (
            <p role="alert" className="text-sm text-destructive">
              {state.error}
            </p>
          )}
        </CardContent>
        <CardFooter className="mt-6 justify-end gap-2">
          <Button
            variant="outline"
            nativeButton={false}
            render={<Link href={cancelHref} />}
          >
            취소
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? "저장 중..." : submitLabel}
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}
