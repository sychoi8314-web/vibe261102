import { Suspense } from "react"
import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import { EyeIcon, ListIcon, PencilIcon } from "lucide-react"

import { CATEGORIES, getPost } from "@/lib/board"
import { formatFull } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { CommentForm } from "@/components/comment-form"
import { DeletePostDialog } from "@/components/delete-post-dialog"
import { ViewCounter } from "@/components/view-counter"

export async function generateMetadata({
  params,
}: PageProps<"/posts/[id]">): Promise<Metadata> {
  const id = Number((await params).id)
  const post = Number.isInteger(id) ? await getPost(id) : null
  return { title: post?.title ?? "글을 찾을 수 없습니다" }
}

export default function PostPage({ params }: PageProps<"/posts/[id]">) {
  return (
    <Suspense fallback={<PostSkeleton />}>
      <PostDetail params={params} />
    </Suspense>
  )
}

async function PostDetail({
  params,
}: {
  params: PageProps<"/posts/[id]">["params"]
}) {
  const id = Number((await params).id)
  const post = Number.isInteger(id) ? await getPost(id) : null
  if (!post) notFound()

  return (
    <div className="flex flex-col gap-6">
      <ViewCounter postId={post.id} />

      <Card>
        <CardHeader className="gap-3">
          <div>
            <Badge variant={post.category === "notice" ? "default" : "secondary"}>
              {CATEGORIES[post.category]}
            </Badge>
          </div>
          <CardTitle className="text-xl leading-snug break-words">
            {post.title}
          </CardTitle>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{post.author}</span>
            <span>{formatFull(post.createdAt)}</span>
            {post.updatedAt && <span>(수정됨 {formatFull(post.updatedAt)})</span>}
            <span className="flex items-center gap-1">
              <EyeIcon className="size-3.5" />
              {post.views}
            </span>
          </div>
        </CardHeader>
        <Separator />
        <CardContent>
          <div className="min-h-40 whitespace-pre-wrap break-words leading-relaxed">
            {post.content}
          </div>
        </CardContent>
        <CardFooter className="justify-between gap-2">
          <Button variant="outline" nativeButton={false} render={<Link href="/" />}>
            <ListIcon data-icon="inline-start" />
            목록
          </Button>
          <div className="flex gap-2">
            <Button
              variant="outline"
              nativeButton={false}
              render={<Link href={`/posts/${post.id}/edit`} />}
            >
              <PencilIcon data-icon="inline-start" />
              수정
            </Button>
            <DeletePostDialog postId={post.id} />
          </div>
        </CardFooter>
      </Card>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">댓글 {post.comments.length}</h2>
        {post.comments.length > 0 && (
          <ul className="flex flex-col divide-y rounded-xl border">
            {post.comments.map((comment) => (
              <li key={comment.id} className="flex flex-col gap-1 p-4">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{comment.author}</span>
                  <span className="text-muted-foreground">
                    {formatFull(comment.createdAt)}
                  </span>
                </div>
                <p className="whitespace-pre-wrap break-words text-sm">
                  {comment.content}
                </p>
              </li>
            ))}
          </ul>
        )}
        <CommentForm postId={post.id} />
      </section>
    </div>
  )
}

function PostSkeleton() {
  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div className="h-5 w-16 animate-pulse rounded bg-muted" />
        <div className="h-7 w-2/3 animate-pulse rounded bg-muted" />
        <div className="h-40 animate-pulse rounded bg-muted" />
      </CardContent>
    </Card>
  )
}
