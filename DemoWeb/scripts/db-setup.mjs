// Creates the board tables and inserts sample posts when the board is empty.
// Usage: npm run db:setup   (reads DATABASE_URL from .env.local)
import { readFile } from "node:fs/promises"
import { randomBytes, scryptSync } from "node:crypto"
import { neon } from "@neondatabase/serverless"

if (!process.env.DATABASE_URL) {
  console.error("DATABASE_URL is not set. Add it to .env.local first.")
  process.exit(1)
}

const sql = neon(process.env.DATABASE_URL)

// Same format as hashPassword() in src/lib/board.ts: "<salt>:<hash>"
function hashPassword(password) {
  const salt = randomBytes(16).toString("hex")
  return `${salt}:${scryptSync(password, salt, 32).toString("hex")}`
}

const schema = await readFile(new URL("../db/schema.sql", import.meta.url), "utf8")
for (const statement of schema.split(";").map((s) => s.trim()).filter(Boolean)) {
  await sql.query(statement)
}
console.log("Schema ready.")

const [{ count }] = await sql`SELECT count(*)::int AS count FROM posts`
if (count > 0) {
  console.log(`Posts table already has ${count} rows; skipping sample data.`)
  process.exit(0)
}

const ago = (hours) => new Date(Date.now() - hours * 3_600_000).toISOString()
const passwordHash = hashPassword("1234")
const samples = [
  {
    category: "notice",
    title: "DemoWeb 게시판에 오신 것을 환영합니다",
    content:
      "자유롭게 글을 작성하고 댓글을 남겨 보세요.\n\n글을 쓸 때 입력한 비밀번호로 나중에 글을 수정하거나 삭제할 수 있습니다.\n(예시 글의 비밀번호는 모두 1234 입니다.)",
    author: "관리자",
    createdAt: ago(72),
    views: 42,
    comments: [],
  },
  {
    category: "free",
    title: "Next.js 16 써보신 분 계신가요?",
    content:
      "Cache Components가 기본으로 켜져 있던데 다들 어떻게 쓰고 계신지 궁금합니다.",
    author: "개발자A",
    createdAt: ago(30),
    views: 17,
    comments: [
      {
        author: "개발자B",
        content: "Suspense 경계만 잘 잡으면 생각보다 편하더라고요.",
        createdAt: ago(28),
      },
    ],
  },
  {
    category: "qna",
    title: "shadcn/ui 컴포넌트 커스터마이징 질문",
    content:
      "버튼 색상을 프로젝트 전체에서 바꾸고 싶은데 globals.css의 CSS 변수만 수정하면 되나요?",
    author: "질문러",
    createdAt: ago(5),
    views: 8,
    comments: [],
  },
  {
    category: "free",
    title: "오늘 점심 뭐 드셨나요",
    content: "저는 김치찌개 먹었습니다 🍲",
    author: "배고픈사람",
    createdAt: ago(1),
    views: 3,
    comments: [],
  },
]

for (const post of samples) {
  const [{ id }] = await sql`
    INSERT INTO posts (category, title, content, author, password_hash, created_at, views)
    VALUES (${post.category}, ${post.title}, ${post.content}, ${post.author},
            ${passwordHash}, ${post.createdAt}, ${post.views})
    RETURNING id`
  for (const comment of post.comments) {
    await sql`
      INSERT INTO comments (post_id, author, content, created_at)
      VALUES (${id}, ${comment.author}, ${comment.content}, ${comment.createdAt})`
  }
}
console.log(`Inserted ${samples.length} sample posts.`)
