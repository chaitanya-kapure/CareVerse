import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "../components/ui/PageHeader";
import Card from "../components/ui/Card";
import Alert from "../components/ui/Alert";
import Button from "../components/ui/Button";
import Spinner from "../components/ui/Spinner";
import EmptyState from "../components/ui/EmptyState";
import Badge from "../components/ui/Badge";
import { useAuth } from "../hooks/useAuth";
import { socialService } from "../services/social.service";
import { getErrorMessage } from "../services/api";
import { formatDateTime } from "../utils/format";
import type { Post, PostType } from "../types";

const POST_TYPES: { value: PostType; label: string }[] = [
  { value: "text", label: "Text Post" },
  { value: "article", label: "Article" },
  { value: "question", label: "Question" },
  { value: "awareness", label: "Awareness Post" },
];

function extractHashtags(text: string): string[] {
  const matches = text.match(/#[a-zA-Z0-9_]+/g);
  if (!matches) return [];
  return Array.from(new Set(matches.map((tag) => tag.slice(1).toLowerCase())));
}

function PostTypeBadge({ type }: { type: PostType }) {
  switch (type) {
    case "article":
      return <Badge tone="info">Article</Badge>;
    case "question":
      return <Badge tone="warning">Question</Badge>;
    case "awareness":
      return <Badge tone="success">Awareness</Badge>;
    case "text":
    default:
      return <Badge tone="neutral">Post</Badge>;
  }
}

function CommentSection({ postId }: { postId: string }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [commentText, setCommentText] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["comments", postId],
    queryFn: () => socialService.listComments(postId),
  });

  const addCommentMutation = useMutation({
    mutationFn: (text: string) => socialService.addComment(postId, text),
    onSuccess: () => {
      setCommentText("");
      queryClient.invalidateQueries({ queryKey: ["comments", postId] });
      queryClient.invalidateQueries({ queryKey: ["feed-posts"] });
    },
  });

  const deleteCommentMutation = useMutation({
    mutationFn: (commentId: string) => socialService.deleteComment(postId, commentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["comments", postId] });
      queryClient.invalidateQueries({ queryKey: ["feed-posts"] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    addCommentMutation.mutate(commentText.trim());
  };

  return (
    <div className="mt-4 border-t border-slate-100 pt-3">
      <form onSubmit={handleSubmit} className="mb-3 flex gap-2">
        <input
          type="text"
          value={commentText}
          onChange={(e) => setCommentText(e.target.value)}
          placeholder="Write a comment..."
          maxLength={1000}
          className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
        />
        <Button
          type="submit"
          size="sm"
          disabled={!commentText.trim()}
          isLoading={addCommentMutation.isPending}
        >
          Reply
        </Button>
      </form>

      {addCommentMutation.error && (
        <Alert tone="danger" className="mb-2">
          {getErrorMessage(addCommentMutation.error, "Could not add comment.")}
        </Alert>
      )}

      {isLoading ? (
        <Spinner label="Loading comments" />
      ) : error ? (
        <Alert tone="danger">
          {getErrorMessage(error, "Could not load comments.")}
        </Alert>
      ) : data?.items.length === 0 ? (
        <p className="py-2 text-xs text-slate-500">No comments yet. Be the first to reply!</p>
      ) : (
        <div className="space-y-2">
          {data?.items.map((comment) => (
            <div
              key={comment.id}
              className="flex items-start justify-between rounded-md bg-slate-50 p-2.5 text-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-800">{comment.author_name}</span>
                  <span className="text-xs text-slate-400">
                    {formatDateTime(comment.created_at)}
                  </span>
                </div>
                <p className="mt-1 text-slate-700 whitespace-pre-wrap">{comment.content}</p>
              </div>
              {user?.id === comment.author_id && (
                <button
                  type="button"
                  onClick={() => deleteCommentMutation.mutate(comment.id)}
                  disabled={deleteCommentMutation.isPending}
                  className="ml-2 text-xs text-red-500 hover:text-red-700"
                  title="Delete comment"
                >
                  Delete
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PostCard({ post }: { post: Post }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [showComments, setShowComments] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [reportReason, setReportReason] = useState("");
  const [reportSuccess, setReportSuccess] = useState(false);

  const likeMutation = useMutation({
    mutationFn: () => socialService.toggleLike(post.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feed-posts"] }),
  });

  const saveMutation = useMutation({
    mutationFn: () => socialService.toggleSave(post.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feed-posts"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => socialService.deletePost(post.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["feed-posts"] }),
  });

  const reportMutation = useMutation({
    mutationFn: (reason: string) => socialService.reportPost(post.id, reason),
    onSuccess: () => {
      setReporting(false);
      setReportReason("");
      setReportSuccess(true);
      setTimeout(() => setReportSuccess(false), 4000);
    },
  });

  const isOwnPost = user?.id === post.author_id;

  return (
    <Card className="mb-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-slate-900">{post.author_name}</span>
            <Badge tone={post.author_role === "doctor" ? "info" : "neutral"}>
              {post.author_role}
            </Badge>
            <PostTypeBadge type={post.post_type} />
          </div>
          <p className="mt-0.5 text-xs text-slate-500">{formatDateTime(post.created_at)}</p>
        </div>

        <div className="flex items-center gap-2">
          {isOwnPost && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (window.confirm("Are you sure you want to delete this post?")) {
                  deleteMutation.mutate();
                }
              }}
              isLoading={deleteMutation.isPending}
              className="text-xs text-red-600 hover:bg-red-50"
            >
              Delete
            </Button>
          )}
          {!isOwnPost && (
            <button
              type="button"
              onClick={() => setReporting(!reporting)}
              className="text-xs text-slate-400 hover:text-slate-600"
              title="Report post"
            >
              Report
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 text-sm text-slate-800 whitespace-pre-wrap">{post.content}</div>

      {post.hashtags && post.hashtags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {post.hashtags.map((tag) => (
            <span
              key={tag}
              className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-teal-700"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      {reporting && (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-medium text-slate-700 mb-1">Reason for reporting:</p>
          <div className="flex gap-2">
            <input
              type="text"
              value={reportReason}
              onChange={(e) => setReportReason(e.target.value)}
              placeholder="e.g. Misinformation, spam, inappropriate..."
              className="flex-1 rounded-md border border-slate-300 px-2.5 py-1 text-xs focus:outline-teal-600"
            />
            <Button
              size="sm"
              disabled={!reportReason.trim()}
              isLoading={reportMutation.isPending}
              onClick={() => reportMutation.mutate(reportReason.trim())}
            >
              Submit Report
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setReporting(false)}
            >
              Cancel
            </Button>
          </div>
          {reportMutation.error && (
            <p className="mt-1 text-xs text-red-600">
              {getErrorMessage(reportMutation.error, "Could not submit report.")}
            </p>
          )}
        </div>
      )}

      {reportSuccess && (
        <Alert tone="success" className="mt-2 text-xs">
          Thank you. The post has been flagged for review.
        </Alert>
      )}

      <div className="mt-4 flex items-center gap-4 border-t border-slate-100 pt-3 text-xs text-slate-600">
        <button
          type="button"
          onClick={() => likeMutation.mutate()}
          className={`flex items-center gap-1.5 font-medium transition-colors ${
            post.viewer_has_liked
              ? "text-teal-700 font-semibold"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <span className="text-sm">{post.viewer_has_liked ? "♥" : "♡"}</span>
          <span>{post.like_count} {post.like_count === 1 ? "Like" : "Likes"}</span>
        </button>

        <button
          type="button"
          onClick={() => setShowComments(!showComments)}
          className="flex items-center gap-1.5 font-medium text-slate-600 hover:text-slate-900 transition-colors"
        >
          <span>💬</span>
          <span>{post.comment_count} {post.comment_count === 1 ? "Comment" : "Comments"}</span>
        </button>

        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          className={`flex items-center gap-1.5 font-medium transition-colors ml-auto ${
            post.viewer_has_saved
              ? "text-teal-700 font-semibold"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          <span>{post.viewer_has_saved ? "★" : "☆"}</span>
          <span>{post.viewer_has_saved ? "Saved" : "Save"}</span>
        </button>
      </div>

      {showComments && <CommentSection postId={post.id} />}
    </Card>
  );
}

function PostComposer() {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [postType, setPostType] = useState<PostType>("text");

  const createMutation = useMutation({
    mutationFn: () => {
      const hashtags = extractHashtags(content);
      return socialService.createPost({
        content: content.trim(),
        post_type: postType,
        hashtags,
      });
    },
    onSuccess: () => {
      setContent("");
      setPostType("text");
      queryClient.invalidateQueries({ queryKey: ["feed-posts"] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    createMutation.mutate();
  };

  return (
    <Card title="What's on your mind?" className="mb-6">
      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Share health updates, clinical insights, awareness tips, or questions... Use #hashtags to categorize."
          rows={3}
          maxLength={2000}
          className="w-full rounded-md border border-slate-300 p-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
        />

        {createMutation.error && (
          <Alert tone="danger">
            {getErrorMessage(createMutation.error, "Could not publish post.")}
          </Alert>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <label htmlFor="post-type-select" className="text-xs font-medium text-slate-600">
              Type:
            </label>
            <select
              id="post-type-select"
              value={postType}
              onChange={(e) => setPostType(e.target.value as PostType)}
              className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-700 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
            >
              {POST_TYPES.map((pt) => (
                <option key={pt.value} value={pt.value}>
                  {pt.label}
                </option>
              ))}
            </select>
          </div>

          <Button
            type="submit"
            size="sm"
            disabled={!content.trim()}
            isLoading={createMutation.isPending}
          >
            Publish Post
          </Button>
        </div>
      </form>
    </Card>
  );
}

export default function FeedPage() {
  const [limit, setLimit] = useState(20);

  const { data, isLoading, error } = useQuery({
    queryKey: ["feed-posts", limit],
    queryFn: () => socialService.listPosts(0, limit),
  });

  const posts = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasMore = posts.length < total;

  return (
    <>
      <PageHeader
        title="Social Feed"
        description="Share health insights, questions, and public awareness updates with the CareVerse community."
      />

      <PostComposer />

      {isLoading ? (
        <div className="py-12">
          <Spinner label="Loading feed" />
        </div>
      ) : error ? (
        <Alert tone="danger" title="Could not load feed">
          {getErrorMessage(error, "Please try again later.")}
        </Alert>
      ) : posts.length === 0 ? (
        <EmptyState
          title="No posts yet"
          description="Be the first to share an update, clinical question, or health awareness tip!"
        />
      ) : (
        <div className="space-y-4">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}

          {hasMore && (
            <div className="flex justify-center pt-4">
              <Button
                variant="secondary"
                onClick={() => setLimit((prev) => prev + 20)}
              >
                Load more posts
              </Button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
